import math

from flask_wtf import FlaskForm
from wtforms import BooleanField, DateField, DecimalField, FileField, FloatField, PasswordField, SelectField, StringField, SubmitField, TextAreaField, TimeField
from wtforms.validators import DataRequired, Email, EqualTo, Length, NumberRange, Optional, Regexp, ValidationError

from app.models.user import User


class RegistrationForm(FlaskForm):
    full_name = StringField("Full name", validators=[DataRequired(), Length(min=2, max=100)])
    username = StringField("Username", validators=[DataRequired(), Length(min=3, max=32), Regexp(r"^[A-Za-z0-9_.-]+$", message="Use letters, numbers, dots, underscores, or hyphens.")])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=255)])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=10, max=128)])
    confirm_password = PasswordField("Confirm password", validators=[DataRequired(), EqualTo("password", message="Passwords must match.")])
    submit = SubmitField("Create account")

    def validate_username(self, field):
        if User.query.filter_by(username=field.data.strip()).first():
            raise ValidationError("That username is already in use.")

    def validate_email(self, field):
        if User.query.filter_by(email=field.data.strip().lower()).first():
            raise ValidationError("An account with that email already exists.")


class LoginForm(FlaskForm):
    email = StringField("Email or username", validators=[DataRequired(), Length(min=3, max=255)])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=1, max=128)])
    submit = SubmitField("Sign in")


class ProfileForm(FlaskForm):
    full_name = StringField("Full name", validators=[DataRequired(), Length(min=2, max=100)])
    username = StringField("Username", validators=[DataRequired(), Length(min=3, max=32), Regexp(r"^[A-Za-z0-9_.-]+$", message="Use letters, numbers, dots, underscores, or hyphens.")])
    submit = SubmitField("Save changes")

    def __init__(self, original_username, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.original_username = original_username

    def validate_username(self, field):
        if field.data.strip() != self.original_username and User.query.filter_by(username=field.data.strip()).first():
            raise ValidationError("That username is already in use.")


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField("Current password", validators=[DataRequired(), Length(min=1, max=128)])
    new_password = PasswordField("New password", validators=[DataRequired(), Length(min=10, max=128)])
    confirm_password = PasswordField("Confirm new password", validators=[DataRequired(), EqualTo("new_password", message="Passwords must match.")])
    submit = SubmitField("Update password")


ITEM_CATEGORIES = [
    ("Accessories", "Accessories"), ("Bags", "Bags"), ("Books", "Books"),
    ("Clothing", "Clothing"), ("Electronics", "Electronics"),
    ("Keys", "Keys"), ("Other", "Other"), ("Pets", "Pets"),
    ("Sports", "Sports"), ("Wallets", "Wallets"),
]


class ItemReportForm(FlaskForm):
    title = StringField("Item name", validators=[DataRequired(), Length(min=2, max=120)])
    category = SelectField("Category", choices=ITEM_CATEGORIES, validators=[DataRequired()])
    description = TextAreaField("Description", validators=[DataRequired(), Length(min=10, max=3000)])
    brand = StringField("Brand", validators=[Optional(), Length(max=80)])
    color = StringField("Color", validators=[Optional(), Length(max=50)])
    date = DateField("Date lost", format="%Y-%m-%d", validators=[DataRequired()])
    time = TimeField("Approximate time", format="%H:%M", validators=[Optional()])
    location_name = StringField("Approximate location", validators=[DataRequired(), Length(min=2, max=160)])
    latitude = FloatField("Approximate map latitude", validators=[Optional(), NumberRange(min=-90, max=90)])
    longitude = FloatField("Approximate map longitude", validators=[Optional(), NumberRange(min=-180, max=180)])
    share_exact_location = BooleanField("Share exact lost location publicly")
    image = FileField("Photo (optional)")
    private_details = TextAreaField("Private identifying details", validators=[Optional(), Length(max=2000)])
    serial_number = StringField("Serial number (private)", validators=[Optional(), Length(max=120)])
    estimated_value = DecimalField("Estimated value (optional)", places=2, validators=[Optional(), NumberRange(min=0, max=99999999)])
    additional_notes = TextAreaField("Additional notes (private)", validators=[Optional(), Length(max=2000)])
    storage_info = TextAreaField("Storage / hand-over details (private)", validators=[Optional(), Length(max=1000)])
    verification_question_1 = StringField("Private verification question 1", validators=[Optional(), Length(max=180)])
    verification_question_2 = StringField("Private verification question 2", validators=[Optional(), Length(max=180)])
    verification_question_3 = StringField("Private verification question 3", validators=[Optional(), Length(max=180)])
    submit = SubmitField("Publish report")

    def __init__(self, item_type, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.item_type = item_type
        self.date.label.text = "Date lost" if item_type == "LOST" else "Date found"

    def validate_latitude(self, field):
        if field.data is not None and not math.isfinite(field.data):
            raise ValidationError("Enter a valid map latitude.")
        if field.data is not None and self.longitude.data is None:
            raise ValidationError("Choose both map coordinates, or clear the map marker.")

    def validate_longitude(self, field):
        if field.data is not None and not math.isfinite(field.data):
            raise ValidationError("Enter a valid map longitude.")
        if field.data is not None and self.latitude.data is None:
            raise ValidationError("Choose both map coordinates, or clear the map marker.")


class ClaimForm(FlaskForm):
    message = TextAreaField("Why do you believe this is yours?", validators=[DataRequired(), Length(min=10, max=2000)])
    verification_answer_1 = TextAreaField("Share one identifying detail not shown in the listing", validators=[DataRequired(), Length(min=2, max=500)])
    verification_answer_2 = TextAreaField("Describe a mark, contents, or feature only the owner would know", validators=[DataRequired(), Length(min=2, max=500)])
    verification_answer_3 = TextAreaField("Add any other detail that can verify ownership", validators=[Optional(), Length(max=500)])
    submit = SubmitField("Send claim for review")


class ClaimDecisionForm(FlaskForm):
    submit = SubmitField()


class MessageForm(FlaskForm):
    message = TextAreaField("Message", validators=[DataRequired(), Length(min=1, max=3000)])
    submit = SubmitField("Send message")


class ListingReportForm(FlaskForm):
    reason = SelectField("Reason", choices=[
        ("FAKE", "Fake item"), ("SPAM", "Spam"), ("HARASSMENT", "Harassment"),
        ("FRAUD", "Fraud attempt"), ("INAPPROPRIATE", "Inappropriate content"),
        ("DUPLICATE", "Duplicate listing"), ("OTHER", "Other"),
    ], validators=[DataRequired()])
    description = TextAreaField("What should moderators know?", validators=[DataRequired(), Length(min=10, max=2000)])
    submit = SubmitField("Send report")


class RecoveryForm(FlaskForm):
    message = TextAreaField("Message to the owner", validators=[DataRequired(), Length(min=10, max=2000)])
    contact_email = StringField("Your email (optional)", validators=[Optional(), Email(), Length(max=255)])
    submit = SubmitField("Notify the owner")
