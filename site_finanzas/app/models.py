from datetime import date as _date, datetime, timezone
from app import db, login_manager
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    country = db.Column(db.String(100), nullable=True)
    currency_symbol = db.Column(db.String(10), nullable=True, default='$')
    currency_code = db.Column(db.String(10), nullable=True, default='USD')
    currency_locale = db.Column(db.String(20), nullable=True, default='es')
    usd_rate = db.Column(db.Numeric(12, 4), nullable=True)  # 1 USD = N moneda local; null si la moneda principal es USD
    role = db.Column(db.String(20), nullable=False, default='user')
    is_first_admin = db.Column(db.Boolean, nullable=False, default=False)
    language = db.Column(db.String(5), nullable=True, default='es')
    theme = db.Column(db.String(20), nullable=True, default='dark')
    has_seen_onboarding = db.Column(db.Boolean, nullable=False, default=False)
    help_mode_enabled = db.Column(db.Boolean, nullable=False, default=True)
    mfa_enabled = db.Column(db.Boolean, nullable=False, default=False)
    mfa_secret_encrypted = db.Column(db.LargeBinary, nullable=True)
    weekly_report_enabled = db.Column(db.Boolean, nullable=False, default=False)

    @property
    def is_admin(self):
        return self.role == 'admin'

    transactions = db.relationship('Transaction', backref='user', lazy=True,
                                   cascade='all, delete-orphan')
    budgets = db.relationship('Budget', backref='user', lazy=True,
                              cascade='all, delete-orphan')
    categories = db.relationship('Category', backref='owner', lazy=True,
                                 cascade='all, delete-orphan',
                                 foreign_keys='Category.user_id')
    years = db.relationship('UserYear', backref='user', lazy=True,
                            cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'


class UserYear(db.Model):
    __tablename__ = 'user_years'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    year = db.Column(db.Integer, nullable=False)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'year', name='uq_user_year'),
    )

    def __repr__(self):
        return f'<UserYear {self.year}>'


class Category(db.Model):
    __tablename__ = 'categories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    type = db.Column(db.String(10), nullable=False)  # 'income' or 'expense'
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    color = db.Column(db.String(7), nullable=True)

    transactions = db.relationship('Transaction', backref='category', lazy=True)

    def __repr__(self):
        return f'<Category {self.name}>'


class Transaction(db.Model):
    __tablename__ = 'transactions'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False)
    type = db.Column(db.String(10), nullable=False)  # 'income' or 'expense'
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    description = db.Column(db.String(200), nullable=True)
    date = db.Column(db.Date, nullable=False, default=_date.today)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    is_demo = db.Column(db.Boolean, nullable=False, default=False)
    recurring_id = db.Column(db.Integer, nullable=True)

    def __repr__(self):
        return f'<Transaction {self.type} {self.amount}>'


class Budget(db.Model):
    __tablename__ = 'budgets'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    month = db.Column(db.Integer, nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'year', 'month', name='uq_user_budget'),
    )

    def __repr__(self):
        return f'<Budget {self.year}/{self.month} {self.amount}>'


class AppConfig(db.Model):
    __tablename__ = 'app_config'
    id = db.Column(db.Integer, primary_key=True)
    allow_registration = db.Column(db.Boolean, nullable=False, default=True)

    @staticmethod
    def get():
        config = AppConfig.query.first()
        if config is None:
            config = AppConfig(allow_registration=True)
            db.session.add(config)
            db.session.commit()
        return config

    def __repr__(self):
        return f'<AppConfig allow_registration={self.allow_registration}>'


class UserEmailConfig(db.Model):
    __tablename__ = 'user_email_config'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)
    smtp_enabled = db.Column(db.Boolean, default=False, nullable=False)
    smtp_host = db.Column(db.String(120), nullable=True)
    smtp_port = db.Column(db.Integer, nullable=True)
    smtp_username = db.Column(db.String(120), nullable=True)
    smtp_password_encrypted = db.Column(db.LargeBinary, nullable=True)
    smtp_use_tls = db.Column(db.Boolean, default=True, nullable=False)
    smtp_use_ssl = db.Column(db.Boolean, default=False, nullable=False)
    sender_email = db.Column(db.String(120), nullable=True)
    sender_name = db.Column(db.String(120), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    user = db.relationship('User', backref=db.backref('email_config', uselist=False, cascade='all, delete-orphan'))

    def __repr__(self):
        return f'<UserEmailConfig user_id={self.user_id} enabled={self.smtp_enabled}>'


class CategoryBudget(db.Model):
    """Monthly spending limit for a specific category, scoped to a year+month period."""
    __tablename__ = 'category_budgets'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    month = db.Column(db.Integer, nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        db.UniqueConstraint('user_id', 'year', 'month', 'category_id', name='uq_user_year_month_cat_budget'),
    )

    user = db.relationship('User', backref=db.backref('category_budgets', lazy=True,
                                                       cascade='all, delete-orphan'))
    category = db.relationship('Category')

    def __repr__(self):
        return f'<CategoryBudget user={self.user_id} y={self.year} m={self.month} cat={self.category_id}>'


class UserSeenAnnouncement(db.Model):
    __tablename__ = 'user_seen_announcements'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    announcement_key = db.Column(db.String(50), nullable=False)
    seen_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        db.UniqueConstraint('user_id', 'announcement_key', name='uq_user_announcement'),
    )

    user = db.relationship('User', backref=db.backref('seen_announcements', lazy=True,
                                                       cascade='all, delete-orphan'))

    def __repr__(self):
        return f'<UserSeenAnnouncement user={self.user_id} key={self.announcement_key}>'


class PasswordResetToken(db.Model):
    __tablename__ = 'password_reset_token'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    token_hash = db.Column(db.String(64), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    expires_at = db.Column(db.DateTime, nullable=False)
    used_at = db.Column(db.DateTime, nullable=True)
    request_ip = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.String(512), nullable=True)

    user = db.relationship('User', backref=db.backref('reset_tokens', lazy=True, cascade='all, delete-orphan'))

    def __repr__(self):
        return f'<PasswordResetToken user_id={self.user_id} expires={self.expires_at}>'


class RecurringTransaction(db.Model):
    __tablename__ = 'recurring_transactions'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False)
    type = db.Column(db.String(10), nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    description = db.Column(db.String(200), nullable=True)
    day_of_month = db.Column(db.Integer, nullable=False, default=1)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    end_date = db.Column(db.Date, nullable=True)
    is_demo = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    user = db.relationship('User', backref=db.backref('recurring_transactions', lazy=True,
                                                       cascade='all, delete-orphan'))
    category = db.relationship('Category')

    def __repr__(self):
        return f'<RecurringTransaction {self.type} {self.amount} day={self.day_of_month}>'


class SavingsGoal(db.Model):
    __tablename__ = 'savings_goals'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    target_amount = db.Column(db.Numeric(12, 2), nullable=False)
    current_amount = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    target_date = db.Column(db.Date, nullable=True)
    description = db.Column(db.String(200), nullable=True)
    is_completed = db.Column(db.Boolean, nullable=False, default=False)
    is_demo = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    user = db.relationship('User', backref=db.backref('savings_goals', lazy=True,
                                                       cascade='all, delete-orphan'))

    @property
    def progress_pct(self):
        if not self.target_amount or self.target_amount <= 0:
            return 100.0
        return min(float(self.current_amount) / float(self.target_amount) * 100, 100.0)

    @property
    def remaining(self):
        return max(float(self.target_amount) - float(self.current_amount), 0.0)

    @property
    def days_left(self):
        if not self.target_date:
            return None
        from datetime import date as _d
        return (self.target_date - _d.today()).days

    def __repr__(self):
        return f'<SavingsGoal {self.name} {self.current_amount}/{self.target_amount}>'


class CustomBudget(db.Model):
    """One free-range budget per user, linked to an auto-created expense category."""
    __tablename__ = 'custom_budgets'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))



    user = db.relationship('User', backref=db.backref('custom_budgets', lazy=True,
                                                       cascade='all, delete-orphan'))
    category = db.relationship('Category')

    def __repr__(self):
        return f'<CustomBudget {self.name} {self.amount}>'


class DemoState(db.Model):
    """Tracks which years were created by demo data. Used to restore state on reset."""
    __tablename__ = 'demo_state'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True)
    pre_demo_years = db.Column(db.Text, nullable=False, default='[]')
    demo_years = db.Column(db.Text, nullable=False, default='[]')
    loaded_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    user = db.relationship('User', backref=db.backref('demo_state', uselist=False,
                                                       cascade='all, delete-orphan'))

    def __repr__(self):
        return f'<DemoState user={self.user_id}>'


class UsdCategory(db.Model):
    """Expense category for the standalone USD section."""
    __tablename__ = 'usd_categories'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(50), nullable=False)
    color = db.Column(db.String(7), nullable=True)
    is_demo = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        db.UniqueConstraint('user_id', 'name', name='uq_usd_category_user_name'),
    )

    user = db.relationship('User', backref=db.backref('usd_categories', lazy=True,
                                                       cascade='all, delete-orphan'))

    def __repr__(self):
        return f'<UsdCategory {self.name}>'


class UsdTransaction(db.Model):
    """Expense entry in the standalone USD section."""
    __tablename__ = 'usd_transactions'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('usd_categories.id'), nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    description = db.Column(db.String(200), nullable=True)
    date = db.Column(db.Date, nullable=False, default=_date.today)
    is_demo = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    user = db.relationship('User', backref=db.backref('usd_transactions', lazy=True,
                                                       cascade='all, delete-orphan'))
    category = db.relationship('UsdCategory', backref=db.backref('transactions', lazy=True,
                                                                  cascade='all, delete-orphan'))

    def __repr__(self):
        return f'<UsdTransaction {self.amount} {self.date}>'


class UsdBudget(db.Model):
    """Monthly USD budget per user."""
    __tablename__ = 'usd_budgets'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    month = db.Column(db.Integer, nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    is_demo = db.Column(db.Boolean, nullable=False, default=False)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'year', 'month', name='uq_usd_budget'),
    )

    user = db.relationship('User', backref=db.backref('usd_budgets', lazy=True,
                                                       cascade='all, delete-orphan'))

    def __repr__(self):
        return f'<UsdBudget {self.year}/{self.month} {self.amount}>'


class AuditLog(db.Model):
    """Security and application event log. user_id is nullable (pre-auth events)."""
    __tablename__ = 'audit_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    event_type = db.Column(db.String(50), nullable=False, index=True)
    description = db.Column(db.String(500), nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False,
                           default=lambda: datetime.now(timezone.utc), index=True)

    user = db.relationship('User', backref=db.backref('audit_logs', lazy=True,
                                                       passive_deletes=True))

    def __repr__(self):
        return f'<AuditLog {self.event_type} user={self.user_id}>'
