import re
from flask_wtf import FlaskForm
from flask_babel import lazy_gettext as _l, gettext as _
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError
from app.models import User


def validate_password_policy(form, field):
    password = field.data
    if len(password) < 10:
        raise ValidationError(_('La contraseña debe tener al menos 10 caracteres.'))
    if not re.search(r"[A-Z]", password):
        raise ValidationError(_('La contraseña debe incluir al menos una letra mayúscula.'))
    if not re.search(r"[a-z]", password):
        raise ValidationError(_('La contraseña debe incluir al menos una letra minúscula.'))
    if not re.search(r"\d", password):
        raise ValidationError(_('La contraseña debe incluir al menos un número.'))
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        raise ValidationError(_('La contraseña debe incluir al menos un carácter especial.'))


class RegisterForm(FlaskForm):
    username = StringField(_l('Usuario'), validators=[DataRequired(), Length(min=3, max=80)])
    email = StringField(_l('Email'), validators=[DataRequired(), Email()])
    password = PasswordField(_l('Contraseña'), validators=[DataRequired(), validate_password_policy])
    confirm_password = PasswordField(
        _l('Confirmar Contraseña'),
        validators=[DataRequired(), EqualTo('password', message=_l('Las contraseñas no coinciden.'))]
    )
    submit = SubmitField(_l('Registrarse'))

    def validate_username(self, username):
        if User.query.filter_by(username=username.data).first():
            raise ValidationError(_('Ese nombre de usuario ya está en uso.'))

    def validate_email(self, email):
        if User.query.filter_by(email=email.data).first():
            raise ValidationError(_('Ese email ya está registrado.'))


class LoginForm(FlaskForm):
    email = StringField(_l('Email'), validators=[DataRequired(), Email()])
    password = PasswordField(_l('Contraseña'), validators=[DataRequired()])
    remember = BooleanField(_l('Recordarme'))
    submit = SubmitField(_l('Iniciar Sesión'))


class MFAVerifyForm(FlaskForm):
    code = StringField(_l('Código de verificación'), validators=[DataRequired(), Length(min=6, max=6)])
    submit = SubmitField(_l('Verificar'))


class ForgotPasswordForm(FlaskForm):
    email = StringField(_l('Email'), validators=[DataRequired(), Email()])
    submit = SubmitField(_l('Enviar Enlace de Recuperación'))


class ResetPasswordForm(FlaskForm):
    password = PasswordField(_l('Nueva Contraseña'), validators=[DataRequired(), validate_password_policy])
    confirm_password = PasswordField(
        _l('Confirmar Contraseña'),
        validators=[DataRequired(), EqualTo('password', message=_l('Las contraseñas no coinciden.'))]
    )
    submit = SubmitField(_l('Restablecer Contraseña'))
