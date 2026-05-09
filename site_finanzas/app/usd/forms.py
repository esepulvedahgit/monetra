from flask_wtf import FlaskForm
from wtforms import StringField, DecimalField, DateField, SelectField
from wtforms.validators import DataRequired, NumberRange, Length, Optional
from flask_babel import lazy_gettext as _l


class UsdCategoryForm(FlaskForm):
    name = StringField(_l('Nombre'), validators=[DataRequired(), Length(max=50)])


class UsdTransactionForm(FlaskForm):
    date = DateField(_l('Fecha'), validators=[DataRequired()])
    category_id = SelectField(_l('Categoría'), coerce=int, validators=[DataRequired()])
    amount = DecimalField(_l('Monto USD'), places=2, validators=[
        DataRequired(), NumberRange(min=0.01)
    ])
    description = StringField(_l('Descripción'), validators=[Optional(), Length(max=200)])


class UsdBudgetForm(FlaskForm):
    amount = DecimalField(_l('Presupuesto mensual USD'), places=2, validators=[
        DataRequired(), NumberRange(min=0)
    ])
