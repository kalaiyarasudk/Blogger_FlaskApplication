from flask import Flask, render_template, url_for, flash, redirect, request, abort
from flaskblog.forms import (RegisterationForm, LoginForm, UpdateAccountForm, 
            PostForm, RequestResetForm,RestPasswordForm)
from flaskblog.models import User, Post
from flaskblog import app, bcrypt,db,mail
from flask_login import login_user, current_user, logout_user, login_required
import secrets
import os
from flask_mail import Message
import smtplib



@app.route('/')
@app.route('/home')
def home():
    page = request.args.get('page',1,type=int)
    posts = Post.query.order_by(Post.date_posted.desc()).paginate(page=page,per_page = 5)
    return render_template('home.html', posts = posts)


@app.route('/about')
def about():
    return render_template('about.html',title = 'About')



@app.route('/register', methods=['GET','POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = RegisterationForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user = User(username=form.username.data,
                email = form.email.data,
                password = hashed_password)
        db.session.add(user)
        db.session.commit()
        flash(f'Account created , you can able to login!', 'success')
        return redirect(url_for('login'))
    return render_template('register.html',title='Register',form=form)

@app.route('/login',methods=['GET','POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and bcrypt.check_password_hash(user.password,form.password.data):
            login_user(user,remember=form.remember.data)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('home'))
        else:
            flash(f"Login unsucessfull. pls check the email or password", 'danger')
    return render_template('login.html',title='login',form=form)

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('home'))


def save_picture(form_picture):
    random_hex = secrets.token_hex(8)
    f_name , f_ext = os.path.splitext(form_picture.filename)
    picture_fn = random_hex + f_ext
    picture_path = os.path.join(app.root_path,'static/profile_pic',picture_fn)
    form_picture.save(picture_path)
    return picture_fn

@app.route('/account', methods=['GET','POST'])
@login_required
def account():
    form = UpdateAccountForm()
    if form.validate_on_submit():
        if form.picture.data:
            picture_file = save_picture(form.picture.data)
            current_user.image_file = picture_file

        current_user.username = form.username.data
        current_user.email = form.email.data
        db.session.commit()
        flash('Your account has updated!', 'success')
        return redirect(url_for('account'))
    elif request.method == 'GET':
        form.username.data = current_user.username
        form.email.data = current_user.email
    image_file = url_for('static', filename='profile_pic/' + current_user.image_file)
    return render_template('account.html',title='account', image_file = image_file, form = form)

@app.route('/post/new',methods=['GET','POST'])
@login_required
def new_post():
    form = PostForm()
    if form.validate_on_submit():
        post = Post(title=form.title.data, content = form.content.data, author = current_user)
        db.session.add(post)
        db.session.commit()
        flash('The post has been created!','success')
        return redirect(url_for('home'))

    return render_template('create_post.html',title='New Post', form=form, legend='New post')

@app.route('/post/<int:post_id>')
def post(post_id):
    post = Post.query.get_or_404(post_id)
    return render_template('post.html',title='post.title',post=post)

@app.route('/post/<int:post_id>/update', methods=['GET','POST'])
@login_required
def update_post(post_id):
    post = Post.query.get_or_404(post_id)
    if post.author != current_user:
        abort(403)
    form = PostForm()
    if form.validate_on_submit():
        post.title = form.title.data
        post.content = form.content.data
        db.session.commit()
        flash("Your post has been updated!",'success')
        return redirect(url_for('post',post_id=post.id))
    elif request.method == 'GET':
        form.title.data = post.title
        form.content.data = post.content
    return render_template('create_post.html',title='Update post',form=form, legend='Update post' )
        

@app.route('/post/<int:post_id>/delete', methods=['POST'])
@login_required
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    if post.author != current_user:
        abort(403)
    db.session.delete(post)
    db.session.commit()
    flash('Your post has been deleted', 'success')
    return redirect(url_for('home'))


@app.route('/user/<string:username>')
def user_post(username):
    page = request.args.get('page',1,type=int)
    user = User.query.filter_by(username=username).first_or_404()
    posts = Post.query.filter_by(author=user).order_by(Post.date_posted.desc()).paginate(page=page,per_page = 5)
    return render_template('user_post.html', posts = posts,user=user)


def send_reset_email(user):
    token = user.get_reset_token()
    msg = Message('Password Reset Request',
             sender='noreply@demo.com', recipients=[user.email])
    msg.body=f'''To reset your password , visit the following link :
                {url_for('reset_token',token= token, _external=True)}
            '''
    mail.send(msg)

@app.route('/reset_password',methods=['GET','POST'])
def reset_request():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form  = RequestResetForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        send_reset_email(user)
        flash("An email has been send to reset a password",'info')
        return redirect(url_for('login'))
    return render_template('rest_request.html', title='Reset Password', form=form)

@app.route('/reset_password/<token>',methods=['GET','POST'])
def reset_token(token):
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    user = User.verify_reset_token(token)
    if user is None:
        flash('This is a invalid token','warning')
        return redirect(url_for('reset_request'))
    form = RestPasswordForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user.password = hashed_password
        db.session.commit()
        flash(f'your password hase been updated', 'success')
        return redirect(url_for('login'))
    return render_template('rest_token.html', title='Reset Password', form=form)
