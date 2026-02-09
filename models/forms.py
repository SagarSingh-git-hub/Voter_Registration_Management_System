from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField, DateField, FileField, HiddenField
from wtforms.validators import DataRequired, Length, Email, EqualTo, ValidationError, Regexp
from models.user import User
from models import mongo

class RegistrationForm(FlaskForm):
    username = StringField('User ID (Choose a unique ID)', validators=[DataRequired(), Length(min=4, max=20)])
    full_name = StringField('Full Name', validators=[DataRequired(), Length(min=2, max=50)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Register')

    def validate_username(self, username):
        user = User.find_by_username(username.data)
        if user:
            raise ValidationError('This User ID is already taken. Please choose a different one.')

class OTPForm(FlaskForm):
    otp = StringField('OTP', validators=[DataRequired(), Length(min=6, max=6)])
    submit = SubmitField('Verify')

class ForgotPasswordForm(FlaskForm):
    email = StringField('Email Address', validators=[DataRequired(), Email()])
    submit = SubmitField('Send Reset Link')

class LoginForm(FlaskForm):
    username = StringField('User ID', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    login_mode = HiddenField('Login Mode', default='citizen')
    submit = SubmitField('Login')

class VoterApplicationForm(FlaskForm):
    # 1. Personal Details
    full_name = StringField('Full Name', validators=[DataRequired()])
    relative_name = StringField('Relative Name', validators=[DataRequired()])
    relative_type = SelectField('Relationship Type', choices=[('Father', 'Father'), ('Mother', 'Mother'), ('Spouse', 'Spouse')], validators=[DataRequired()])
    dob = DateField('Date of Birth', format='%Y-%m-%d', validators=[DataRequired()])
    gender = SelectField('Gender', choices=[('', 'Select Gender'), ('Male', 'Male'), ('Female', 'Female'), ('Other', 'Other')], validators=[DataRequired()])
    
    # Contact Details
    phone = StringField('Mobile Number', validators=[DataRequired()])
    email = StringField('Email ID', validators=[Email()]) # Optional
    photograph = FileField('Passport Size Photograph', validators=[DataRequired()])

    # 2. Address Details
    present_address = StringField('Present Address', validators=[DataRequired(), Length(min=10)])
    permanent_address = StringField('Permanent Address', validators=[DataRequired(), Length(min=10)])
    pin_code = StringField('PIN Code', validators=[DataRequired(), Length(min=6, max=6)])
    
    # 3. Electoral Area (Auto-Derived)
    state = SelectField('State', choices=[], validators=[DataRequired()], validate_choice=False)
    district = SelectField('District', choices=[], validators=[DataRequired()], validate_choice=False)
    assembly_constituency = StringField('Assembly Constituency', validators=[DataRequired()]) # Auto-filled
    loksabha_constituency = StringField('Lok Sabha Constituency', validators=[DataRequired()]) # Auto-filled
    
    # Admin Only Fields
    polling_station = StringField('Polling Station') # Optional/Admin only
    booth_number = StringField('Booth Number') # Optional/Admin only

    # 4. Identity Proof
    id_proof_type = SelectField('ID Proof Type', choices=[
        ('', 'Select ID Proof'),
        ('Aadhar Card', 'Aadhar Card'),
        ('PAN Card', 'PAN Card'),
        ('Voter Card', 'Voter Card'),
        ('Driving License', 'Driving License'),
        ('Birth Certificate', 'Birth Certificate')
    ], validators=[DataRequired()])
    id_proof_number = StringField('ID Proof Number', validators=[DataRequired()])
    document = FileField('Upload ID Proof Document', validators=[DataRequired()])
    
    submit_application = SubmitField('Submit Application')

    def validate_phone(self, field):
        import re
        # Normalize: Remove non-digits
        raw_number = re.sub(r'\D', '', field.data)
        
        # Handle country code (+91 or 0 prefix)
        # If length is 11 (starting with 0) or 12 (starting with 91), strip it
        if len(raw_number) > 10:
            if raw_number.startswith('91') and len(raw_number) == 12:
                raw_number = raw_number[2:]
            elif raw_number.startswith('0') and len(raw_number) == 11:
                raw_number = raw_number[1:]
        
        # Update field data with normalized number
        field.data = raw_number
        
        # Strict Validation Rules
        
        # 1. Check Length
        if len(raw_number) != 10:
            raise ValidationError('Mobile number must be exactly 10 digits.')
            
        # 2. Check Starting Digit (6, 7, 8, 9)
        if not re.match(r'^[6-9]', raw_number):
            raise ValidationError('Indian mobile numbers start with 6, 7, 8, or 9.')
            
        # 3. Check for Dummy/Repeating Numbers (e.g., 0000000000, 1111111111)
        if len(set(raw_number)) == 1:
            raise ValidationError('Invalid or fake mobile number detected.')
            
        # 4. Final Regex Check (Redundant but safe)
        if not re.match(r'^[6-9][0-9]{9}$', raw_number):
             raise ValidationError('Invalid mobile number format.')

    def validate_id_proof_number(self, field):
        import re
        id_type = self.id_proof_type.data
        number = field.data.upper().strip() # Normalize

        if id_type == 'Aadhar Card':
            # 12 digits, spaces allowed/handled
            # Regex: ^[0-9]{4}\s[0-9]{4}\s[0-9]{4}$
            if not re.match(r'^[0-9]{4}\s[0-9]{4}\s[0-9]{4}$', number):
                raise ValidationError('Aadhaar must be 12 digits in format: 1234 5678 9012')
            
            # Check for duplicates (One voter = One Aadhaar)
            # Check in Applications
            if mongo.db.applications.find_one({"id_proof_number": number, "id_proof_type": "Aadhar Card"}):
                raise ValidationError('Aadhaar already registered. One voter = one Aadhaar.')
            # Check in Final Voters
            if mongo.db.final_voters.find_one({"id_proof_number": number, "id_proof_type": "Aadhar Card"}):
                raise ValidationError('Aadhaar already registered. One voter = one Aadhaar.')
        
        elif id_type == 'PAN Card':
            # ^[A-Z]{5}[0-9]{4}[A-Z]{1}$
            if not re.match(r'^[A-Z]{5}[0-9]{4}[A-Z]{1}$', number):
                raise ValidationError('Invalid PAN format. Example: ABCDE1234F')
                
        elif id_type == 'Voter Card':
            # ^[A-Z]{3}[0-9]{7}$
            if not re.match(r'^[A-Z]{3}[0-9]{7}$', number):
                raise ValidationError('Invalid Voter ID format. Example: ABC1234567')
                
        elif id_type == 'Driving License':
            # ^[A-Z]{2}[- ]?[0-9]{2}[- ]?[0-9]{4}[- ]?[0-9]{7}$
            if not re.match(r'^[A-Z]{2}[- ]?[0-9]{2}[- ]?[0-9]{4}[- ]?[0-9]{7}$', number):
                raise ValidationError('Invalid DL format. Example: HR-06-1985-0034761')
                
        elif id_type == 'Birth Certificate':
             # ^[0-9]{3}[ -]?[0-9]{2}[ -]?[0-9]{6}$
            if not re.match(r'^[0-9]{3}[ -]?[0-9]{2}[ -]?[0-9]{6}$', number):
                 raise ValidationError('Invalid Birth Certificate format. Example: 123-21-456789')
