from decimal import Decimal as _Decimal
from flask_wtf import FlaskForm
from flask_babel import lazy_gettext as _l, gettext as _
from wtforms import (StringField, DecimalField, SelectField, TextAreaField,
                     DateField, SubmitField, BooleanField, IntegerField, PasswordField)
from wtforms.validators import DataRequired, NumberRange, Optional, Length, Email, EqualTo, ValidationError
from app.auth.forms import validate_password_policy
from datetime import date


class CleanDecimalField(DecimalField):
    """DecimalField that omits trailing decimal zeros on display.
    300000.00 → '300000', 99.50 → '99.5', 99.99 → '99.99', 0.00 → '0'
    """
    def _value(self):
        if self.raw_data:
            return self.raw_data[0]
        if self.data is not None:
            d = _Decimal(str(self.data))
            if d % 1 == 0:
                return str(int(d))
            s = str(d)
            return s.rstrip('0') if '.' in s else s
        return ''


class ConfigForm(FlaskForm):
    country = SelectField(_l('País'), validators=[DataRequired()])
    currency_symbol = StringField(_l('Símbolo de Moneda'),
                                  validators=[DataRequired(), Length(max=10)])
    submit = SubmitField(_l('Guardar Configuración'))


class TransactionForm(FlaskForm):
    type = SelectField(_l('Tipo'),
                       choices=[('expense', _l('Gasto')), ('income', _l('Ingreso'))],
                       validators=[DataRequired()])
    amount = CleanDecimalField(_l('Monto'), places=2,
                               validators=[DataRequired(), NumberRange(min=0.01)])
    category_id = SelectField(_l('Categoría'), coerce=int, validators=[DataRequired()])
    description = TextAreaField(_l('Descripción'), validators=[Optional(), Length(max=200)])
    date = DateField(_l('Fecha'), validators=[DataRequired()], default=date.today)
    submit = SubmitField(_l('Guardar'))


class CategoryForm(FlaskForm):
    name = StringField(_l('Nombre'), validators=[DataRequired(), Length(max=50)])
    type = SelectField(_l('Tipo'),
                       choices=[('expense', _l('Gasto')), ('income', _l('Ingreso'))],
                       validators=[DataRequired()])
    submit = SubmitField(_l('Crear Categoría'))


class BudgetForm(FlaskForm):
    # choices are set dynamically in the route to support locale-aware month names
    month = SelectField(_l('Mes'), coerce=int, validators=[DataRequired()])
    amount = CleanDecimalField(_l('Monto Presupuesto'), places=2,
                               validators=[DataRequired(), NumberRange(min=0.01)])
    submit = SubmitField(_l('Guardar Presupuesto'))


class CategoryBudgetForm(FlaskForm):
    category_id = SelectField(_l('Categoría'), coerce=int, validators=[DataRequired()])
    amount = CleanDecimalField(_l('Límite mensual'), places=2,
                               validators=[DataRequired(), NumberRange(min=0.01)])
    submit_cat_budget = SubmitField(_l('Guardar'))


class SavingsGoalForm(FlaskForm):
    name = StringField(_l('Nombre de la meta'), validators=[DataRequired(), Length(max=100)])
    target_amount = CleanDecimalField(_l('Monto objetivo'), places=2,
                                      validators=[DataRequired(), NumberRange(min=0.01)])
    current_amount = CleanDecimalField(_l('Monto inicial ahorrado'), places=2,
                                       validators=[Optional(), NumberRange(min=0)], default=0)
    target_date = DateField(_l('Fecha objetivo'), validators=[Optional()])
    description = StringField(_l('Descripción'), validators=[Optional(), Length(max=200)])
    submit = SubmitField(_l('Guardar'))


class RecurringTransactionForm(FlaskForm):
    type = SelectField(_l('Tipo'),
                       choices=[('expense', _l('Gasto')), ('income', _l('Ingreso'))],
                       validators=[DataRequired()])
    amount = CleanDecimalField(_l('Monto'), places=2,
                               validators=[DataRequired(), NumberRange(min=0.01)])
    category_id = SelectField(_l('Categoría'), coerce=int, validators=[DataRequired()])
    description = StringField(_l('Descripción'), validators=[Optional(), Length(max=200)])
    day_of_month = SelectField(_l('Día del mes'), coerce=int,
                               choices=[(i, str(i)) for i in range(1, 29)],
                               validators=[DataRequired()])
    end_date = DateField(_l('Fecha de término'), validators=[Optional()], format='%Y-%m-%d')
    is_active = BooleanField(_l('Activa'))
    submit = SubmitField(_l('Guardar'))


class CustomBudgetForm(FlaskForm):
    name = StringField(_l('Nombre del presupuesto'), validators=[DataRequired(), Length(max=100)])
    amount = CleanDecimalField(_l('Monto'), places=2,
                               validators=[DataRequired(), NumberRange(min=0.01)])
    start_date = DateField(_l('Fecha inicio'), validators=[DataRequired()])
    end_date = DateField(_l('Fecha término'), validators=[DataRequired()])
    submit_custom = SubmitField(_l('Guardar'))

    def validate_end_date(self, field):
        if self.start_date.data and field.data:
            if field.data < self.start_date.data:
                raise ValidationError(_l('La fecha de término debe ser posterior al inicio.'))
            if (field.data - self.start_date.data).days > 365:
                raise ValidationError(_l('El rango máximo es de 365 días.'))


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField(_l('Contraseña actual'), validators=[DataRequired()])
    new_password = PasswordField(_l('Nueva contraseña'),
                                 validators=[DataRequired(), validate_password_policy])
    confirm_password = PasswordField(_l('Confirmar nueva contraseña'),
                                     validators=[DataRequired(),
                                                 EqualTo('new_password', message=_l('Las contraseñas no coinciden.'))])
    submit_password = SubmitField(_l('Cambiar Contraseña'))


class SMTPConfigForm(FlaskForm):
    smtp_enabled = BooleanField(_l('Usar mi propio SMTP'))
    smtp_host = StringField(_l('Servidor SMTP'), validators=[Optional(), Length(max=120)])
    smtp_port = IntegerField(_l('Puerto SMTP'), validators=[Optional(), NumberRange(min=1, max=65535)])
    smtp_username = StringField(_l('Usuario SMTP'), validators=[Optional(), Length(max=120)])
    smtp_password = PasswordField(_l('Contraseña SMTP'), validators=[Optional()])
    smtp_use_tls = BooleanField(_l('Usar TLS'))
    smtp_use_ssl = BooleanField(_l('Usar SSL'))
    sender_email = StringField(_l('Email Remitente'), validators=[Optional(), Email(), Length(max=120)])
    sender_name = StringField(_l('Nombre Remitente'), validators=[Optional(), Length(max=120)])
    submit_smtp = SubmitField(_l('Guardar Configuración SMTP'))

    def validate(self, extra_validators=None):
        rv = FlaskForm.validate(self, extra_validators)
        if not rv:
            return False

        if self.smtp_use_tls.data and self.smtp_use_ssl.data:
            self.smtp_use_tls.errors.append(_('No puedes usar TLS y SSL al mismo tiempo.'))
            self.smtp_use_ssl.errors.append(_('No puedes usar TLS y SSL al mismo tiempo.'))
            return False

        if self.smtp_enabled.data:
            if not self.smtp_host.data:
                self.smtp_host.errors.append(_('Requerido si SMTP está activado.'))
                return False
            if getattr(self, 'require_password', False) and not self.smtp_password.data:
                self.smtp_password.errors.append(_('La contraseña es requerida para activar SMTP.'))
                return False
            if getattr(self, 'require_password', False) == False and not self.smtp_password.data and getattr(self, 'password_is_empty', False):
                self.smtp_password.errors.append(_('La contraseña es obligatoria porque no hay una guardada.'))
                return False
            if not self.smtp_port.data:
                self.smtp_port.errors.append(_('Requerido si SMTP está activado.'))
                return False
            if not self.smtp_username.data:
                self.smtp_username.errors.append(_('Requerido si SMTP está activado.'))
                return False
        return True
