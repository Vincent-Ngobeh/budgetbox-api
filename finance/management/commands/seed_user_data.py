from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from finance.models import BankAccount, Category, Transaction, Budget
from decimal import Decimal
import random
from datetime import date, timedelta


class Command(BaseCommand):
    help = 'Seed any user with complete UK financial data for testing'

    def add_arguments(self, parser):
        parser.add_argument(
            '--user',
            type=str,
            default='testuser',
            help='Username to seed data for (default: testuser)'
        )
        parser.add_argument(
            '--email',
            type=str,
            default=None,
            help='Email for new user (default: <username>@example.com)'
        )
        parser.add_argument(
            '--password',
            type=str,
            default='testpass123',
            help='Password for new user (default: testpass123)'
        )
        parser.add_argument(
            '--accounts',
            type=int,
            default=4,
            help='Number of bank accounts to create (default: 4)'
        )
        parser.add_argument(
            '--transactions',
            type=int,
            default=100,
            help='Approximate number of transactions to create (default: 100)'
        )
        parser.add_argument(
            '--months',
            type=int,
            default=3,
            help='Months of transaction history to generate (default: 3)'
        )
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Delete existing user data before seeding'
        )
        parser.add_argument(
            '--skip-categories',
            action='store_true',
            help='Skip creating categories'
        )
        parser.add_argument(
            '--skip-accounts',
            action='store_true',
            help='Skip creating bank accounts'
        )
        parser.add_argument(
            '--skip-transactions',
            action='store_true',
            help='Skip creating transactions'
        )
        parser.add_argument(
            '--skip-budgets',
            action='store_true',
            help='Skip creating budgets'
        )

    def handle(self, *args, **options):
        username = options['user']
        email = options['email'] or f"{username}@example.com"
        password = options['password']

        self.stdout.write(f'Seeding UK financial data for user: {username}\n')

        # Create or get user
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                'first_name': username.replace('_', ' ').title().split()[0],
                'last_name': username.replace('_', ' ').title().split()[-1] if '_' in username else 'User',
                'email': email
            }
        )

        if created:
            user.set_password(password)
            user.save()
            self.stdout.write(self.style.SUCCESS(f'Created user: {username}'))
        else:
            self.stdout.write(f'User {username} already exists')

        # Reset data if requested
        if options['reset']:
            self._reset_user_data(user)

        # Create auth token
        token, _ = Token.objects.get_or_create(user=user)

        # Create data based on options
        if not options['skip_categories']:
            self._create_categories(user)

        if not options['skip_accounts']:
            self._create_bank_accounts(user, options['accounts'])

        if not options['skip_transactions']:
            self._create_transactions(
                user, options['transactions'], options['months'])

        if not options['skip_budgets']:
            self._create_budgets(user)

        self._print_summary(user, token, password)

    def _reset_user_data(self, user):
        """Delete all existing data for the user"""
        Budget.objects.filter(user=user).delete()
        Transaction.objects.filter(user=user).delete()
        BankAccount.objects.filter(user=user).delete()
        Category.objects.filter(user=user).delete()
        self.stdout.write(self.style.WARNING(
            f'Reset all existing data for {user.username}'))

    def _create_categories(self, user):
        """Create UK-specific income and expense categories"""
        categories = [
            # Income categories
            ('Salary', 'income', True),
            ('Freelance', 'income', True),
            ('Benefits', 'income', False),
            ('Investment Income', 'income', False),
            ('Bonus', 'income', False),
            ('Other Income', 'income', True),

            # Essential expenses
            ('Rent/Mortgage', 'expense', True),
            ('Council Tax', 'expense', True),
            ('Groceries', 'expense', True),
            ('Utilities', 'expense', True),
            ('Insurance', 'expense', True),

            # Transport
            ('Transport', 'expense', True),
            ('TfL/Oyster', 'expense', True),
            ('Petrol', 'expense', False),

            # Subscriptions & Services
            ('Mobile Phone', 'expense', True),
            ('Internet', 'expense', True),
            ('Subscriptions', 'expense', True),

            # Lifestyle
            ('Eating Out', 'expense', True),
            ('Entertainment', 'expense', True),
            ('Shopping', 'expense', True),
            ('Health & Fitness', 'expense', False),
            ('Personal Care', 'expense', False),
            ('Travel', 'expense', False),
            ('Other Expense', 'expense', True),
        ]

        created_count = 0
        for name, cat_type, is_default in categories:
            _, created = Category.objects.get_or_create(
                user=user,
                category_name=name,
                category_type=cat_type,
                defaults={'is_default': is_default}
            )
            if created:
                created_count += 1

        self.stdout.write(
            f'Categories: {created_count} created, {len(categories) - created_count} already existed')

    def _create_bank_accounts(self, user, count):
        """Create UK bank accounts with realistic balances"""
        # UK banks
        uk_banks = [
            'Barclays', 'HSBC', 'Lloyds', 'Santander UK', 'NatWest',
            'TSB', 'Nationwide', 'Metro Bank', 'Monzo', 'Starling Bank'
        ]

        account_templates = [
            {
                'account_name': 'Main Current Account',
                'account_type': 'current',
                'bank_name': random.choice(['Barclays', 'HSBC', 'Lloyds', 'NatWest']),
                'balance_range': (500, 5000),  # Typical current account
            },
            {
                'account_name': 'Savings Account',
                'account_type': 'savings',
                'bank_name': random.choice(['Nationwide', 'Santander UK', 'HSBC']),
                'balance_range': (5000, 25000),  # Emergency fund range
            },
            {
                'account_name': 'ISA Account',
                'account_type': 'savings',
                'bank_name': random.choice(['Nationwide', 'Barclays', 'HSBC']),
                'balance_range': (1000, 20000),  # ISA savings
            },
            {
                'account_name': 'Credit Card',
                'account_type': 'credit',
                'bank_name': random.choice(['Barclays', 'HSBC', 'Lloyds', 'American Express']),
                'balance_range': (-3000, -100),  # Credit card debt
            },
            {
                'account_name': 'Monzo Spending',
                'account_type': 'current',
                'bank_name': 'Monzo',
                'balance_range': (200, 1500),  # Day-to-day spending account
            },
            {
                'account_name': 'Holiday Fund',
                'account_type': 'savings',
                'bank_name': random.choice(['Marcus', 'Starling Bank', 'Chase UK']),
                'balance_range': (500, 5000),  # Goal-based savings
            },
        ]

        created_count = 0
        for i, template in enumerate(account_templates[:count]):
            balance = Decimal(
                str(random.uniform(*template['balance_range']))).quantize(Decimal('0.01'))
            last_four = str(random.randint(1000, 9999))

            _, created = BankAccount.objects.get_or_create(
                user=user,
                account_name=template['account_name'],
                defaults={
                    'account_type': template['account_type'],
                    'bank_name': template['bank_name'],
                    'account_number_masked': f'****{last_four}',
                    'currency': 'GBP',
                    'current_balance': balance,
                    'is_active': True
                }
            )
            if created:
                created_count += 1

        self.stdout.write(
            f'Bank Accounts: {created_count} created, {min(count, len(account_templates)) - created_count} already existed')

    def _create_transactions(self, user, target_count, months):
        """Create realistic UK transactions over the specified months"""
        accounts = list(BankAccount.objects.filter(user=user, is_active=True))
        categories = {
            cat.category_name: cat for cat in Category.objects.filter(user=user)}

        if not accounts or not categories:
            self.stdout.write(self.style.WARNING(
                'No accounts or categories found, skipping transactions'))
            return

        main_account = next(
            (a for a in accounts if 'Current' in a.account_name), accounts[0])
        credit_card = next(
            (a for a in accounts if 'Credit' in a.account_name), main_account)

        today = date.today()
        transactions_data = []

        # UK-specific transaction templates with realistic London prices
        transaction_templates = [
            # Monthly income
            {
                'category': 'Salary',
                'descriptions': ['Monthly Salary Payment', 'Salary - EMPLOYER NAME', 'BACS Payment - Salary'],
                'amount_range': (2500, 4500),  # London median salary range
                'type': 'income',
                'frequency': 'monthly',
                'account': 'main'
            },
            {
                'category': 'Freelance',
                'descriptions': ['Freelance Project Payment', 'Invoice Payment - Client', 'Consulting Fee'],
                'amount_range': (300, 2000),
                'type': 'income',
                'frequency': 'rare',
                'account': 'main'
            },
            {
                'category': 'Bonus',
                'descriptions': ['Annual Bonus', 'Performance Bonus', 'Quarterly Bonus'],
                'amount_range': (500, 3000),
                'type': 'income',
                'frequency': 'rare',
                'account': 'main'
            },

            # Monthly essentials
            {
                'category': 'Rent/Mortgage',
                'descriptions': ['Monthly Rent Payment', 'Mortgage Payment - Halifax', 'Rent - Landlord', 'Standing Order - Rent'],
                'amount_range': (1200, 2500),  # London rent/mortgage
                'type': 'expense',
                'frequency': 'monthly',
                'account': 'main'
            },
            {
                'category': 'Council Tax',
                'descriptions': ['Council Tax - Wandsworth', 'Council Tax Payment', 'Council Tax - Camden', 'Council Tax - Hackney'],
                'amount_range': (120, 200),  # London council tax monthly
                'type': 'expense',
                'frequency': 'monthly',
                'account': 'main'
            },
            {
                'category': 'Utilities',
                'descriptions': ['British Gas - Energy Bill', 'Thames Water', 'EDF Energy', 'Octopus Energy', 'Bulb Energy'],
                'amount_range': (80, 200),  # Combined utilities
                'type': 'expense',
                'frequency': 'monthly',
                'account': 'main'
            },
            {
                'category': 'Insurance',
                'descriptions': ['Aviva Home Insurance', 'Direct Line Car Insurance', 'Vitality Health', 'Admiral Insurance'],
                'amount_range': (25, 150),  # Various insurances
                'type': 'expense',
                'frequency': 'monthly',
                'account': 'main'
            },

            # Monthly services
            {
                'category': 'Mobile Phone',
                'descriptions': ['EE Mobile', 'O2 Mobile', 'Three Mobile', 'Vodafone UK', 'giffgaff'],
                'amount_range': (15, 50),  # Phone contracts
                'type': 'expense',
                'frequency': 'monthly',
                'account': 'main'
            },
            {
                'category': 'Internet',
                'descriptions': ['BT Broadband', 'Virgin Media', 'Sky Broadband', 'TalkTalk', 'Hyperoptic'],
                'amount_range': (25, 60),  # Broadband packages
                'type': 'expense',
                'frequency': 'monthly',
                'account': 'main'
            },
            {
                'category': 'Subscriptions',
                'descriptions': [
                    'Netflix', 'Spotify Premium', 'Amazon Prime', 'Disney+', 'Apple Music',
                    'PureGym Membership', 'The Times Digital', 'PlayStation Plus', 'NOW TV'
                ],
                'amount_range': (5.99, 49.99),  # Various subscriptions
                'type': 'expense',
                'frequency': 'monthly',
                'account': 'main'
            },
            {
                'category': 'TfL/Oyster',
                'descriptions': ['TfL Auto Top-up', 'Oyster Card Top-up', 'Monthly Travelcard Zone 1-3', 'TfL Contactless'],
                'amount_range': (150, 250),  # Monthly London travel
                'type': 'expense',
                'frequency': 'monthly',
                'account': 'main'
            },

            # Weekly - Groceries
            {
                'category': 'Groceries',
                'descriptions': [
                    'Tesco Express', "Sainsbury's Local", 'ASDA Superstore', 'Waitrose & Partners',
                    'M&S Food', 'Lidl GB', 'ALDI', 'Co-op Food', 'Iceland', 'Morrisons'
                ],
                'amount_range': (15, 120),  # Weekly shopping varies
                'type': 'expense',
                'frequency': 'weekly',
                'account': 'main'
            },

            # Frequent - Transport
            {
                'category': 'Transport',
                'descriptions': [
                    'TfL Travel - Zone 1-3', 'Uber Trip', 'Bolt Ride', 'Santander Cycles',
                    'National Rail', 'Citymapper PASS', 'Addison Lee', 'FREE NOW'
                ],
                'amount_range': (3, 40),  # Single trips to daily caps
                'type': 'expense',
                'frequency': 'frequent',
                'account': 'credit'
            },
            {
                'category': 'Petrol',
                'descriptions': ['Shell Petrol Station', 'BP Garage', 'Esso', 'Tesco Petrol', "Sainsbury's Fuel"],
                'amount_range': (40, 80),  # Tank fill-up
                'type': 'expense',
                'frequency': 'occasional',
                'account': 'main'
            },

            # Frequent - Eating Out
            {
                'category': 'Eating Out',
                'descriptions': [
                    'Pret A Manger', 'Costa Coffee', "Nando's", 'Wagamama', 'Pizza Express',
                    'Dishoom', 'Five Guys', 'Leon', 'Honest Burgers', 'Starbucks', 'Greggs',
                    "McDonald's", 'Itsu', 'Wasabi', 'EAT.', "Gail's Bakery", 'Paul UK'
                ],
                'amount_range': (4, 85),  # Coffee to dinner
                'type': 'expense',
                'frequency': 'frequent',
                'account': 'credit'
            },

            # Occasional - Entertainment
            {
                'category': 'Entertainment',
                'descriptions': [
                    'Vue Cinema', 'Odeon Leicester Square', 'National Theatre', 'O2 Arena',
                    'Steam Purchase', 'Apple App Store', 'Ticketmaster', 'London Zoo',
                    'British Museum Donation', 'Eventbrite', 'DICE', 'Royal Albert Hall'
                ],
                'amount_range': (5, 120),  # Various entertainment
                'type': 'expense',
                'frequency': 'occasional',
                'account': 'credit'
            },

            # Occasional - Shopping
            {
                'category': 'Shopping',
                'descriptions': [
                    'Amazon UK', 'John Lewis', 'Marks & Spencer', 'Primark Oxford Street',
                    'IKEA Wembley', 'Argos', 'Next', 'H&M', 'Uniqlo', 'Boots', 'Superdrug',
                    'ASOS', 'Zara', 'TK Maxx', 'Decathlon', 'Currys PC World'
                ],
                'amount_range': (10, 250),  # Various shopping
                'type': 'expense',
                'frequency': 'occasional',
                'account': 'credit'
            },

            # Occasional - Health & Fitness
            {
                'category': 'Health & Fitness',
                'descriptions': [
                    'Boots Pharmacy', 'Holland & Barrett', 'GymBox', "Barry's Bootcamp",
                    'Superdrug', 'NHS Prescription', 'Specsavers', 'Bupa Dental'
                ],
                'amount_range': (10, 150),  # Health purchases to gym classes
                'type': 'expense',
                'frequency': 'occasional',
                'account': 'credit'
            },

            # Occasional - Personal Care
            {
                'category': 'Personal Care',
                'descriptions': [
                    'Haircut - Local Barber', 'Toni & Guy', 'Treatwell Booking',
                    'The Body Shop', 'Lush', 'Space NK'
                ],
                'amount_range': (15, 80),
                'type': 'expense',
                'frequency': 'occasional',
                'account': 'credit'
            },

            # Rare - Travel
            {
                'category': 'Travel',
                'descriptions': [
                    'British Airways', 'easyJet', 'Ryanair', 'Eurostar', 'Booking.com',
                    'Airbnb', 'Hotels.com', 'Trainline', 'National Express'
                ],
                'amount_range': (50, 500),  # Travel bookings
                'type': 'expense',
                'frequency': 'rare',
                'account': 'credit'
            },
        ]

        # Generate transactions for each month
        for month_offset in range(months):
            month_start = (today.replace(day=1) -
                           timedelta(days=month_offset * 30)).replace(day=1)
            days_in_month = 28  # Simplified

            for template in transaction_templates:
                category = categories.get(template['category'])
                if not category:
                    continue

                account = main_account if template['account'] == 'main' else credit_card

                # Determine how many transactions based on frequency
                if template['frequency'] == 'monthly':
                    dates = [month_start +
                             timedelta(days=random.randint(0, 5))]
                elif template['frequency'] == 'weekly':
                    dates = [
                        month_start + timedelta(days=7 * week + random.randint(0, 3)) for week in range(4)]
                elif template['frequency'] == 'frequent':
                    num_trans = random.randint(6, 12)
                    dates = [
                        month_start + timedelta(days=random.randint(0, days_in_month)) for _ in range(num_trans)]
                elif template['frequency'] == 'occasional':
                    num_trans = random.randint(1, 4)
                    dates = [
                        month_start + timedelta(days=random.randint(0, days_in_month)) for _ in range(num_trans)]
                elif template['frequency'] == 'rare':
                    if random.random() < 0.3:  # 30% chance per month
                        dates = [
                            month_start + timedelta(days=random.randint(0, days_in_month))]
                    else:
                        dates = []
                else:
                    dates = []

                for trans_date in dates:
                    if trans_date > today:
                        continue

                    amount = Decimal(
                        str(random.uniform(*template['amount_range']))).quantize(Decimal('0.01'))
                    if template['type'] == 'expense':
                        amount = -amount

                    transactions_data.append({
                        'account': account,
                        'category': category,
                        'description': random.choice(template['descriptions']),
                        'type': template['type'],
                        'amount': amount,
                        'date': trans_date,
                        'is_recurring': template['frequency'] in ['monthly', 'weekly']
                    })

        # Limit to target count (approximately)
        if len(transactions_data) > target_count:
            transactions_data = random.sample(transactions_data, target_count)

        # Create transactions
        created_count = 0
        for trans in transactions_data:
            Transaction.objects.create(
                user=user,
                bank_account=trans['account'],
                category=trans['category'],
                transaction_description=trans['description'],
                transaction_type=trans['type'],
                transaction_amount=trans['amount'],
                transaction_date=trans['date'],
                is_recurring=trans['is_recurring']
            )
            created_count += 1

        self.stdout.write(f'Transactions: {created_count} created')

    def _create_budgets(self, user):
        """Create monthly budgets with realistic London amounts"""
        expense_categories = Category.objects.filter(
            user=user, category_type='expense')

        today = date.today()
        month_start = today.replace(day=1)
        next_month = (month_start + timedelta(days=32)).replace(day=1)
        month_end = next_month - timedelta(days=1)

        # London monthly budget amounts
        budget_configs = [
            ('Rent/Mortgage', 1800),       # London average rent
            ('Council Tax', 150),          # Band D average
            ('Groceries', 400),            # £100/week for groceries
            ('Utilities', 150),            # Gas, electric, water
            ('TfL/Oyster', 200),           # Zone 1-3 travelcard
            ('Transport', 100),            # Additional transport (Uber, etc.)
            ('Eating Out', 250),           # Social dining budget
            ('Entertainment', 150),        # Cinema, events, etc.
            ('Shopping', 200),             # General shopping
            ('Subscriptions', 75),         # Various subscriptions
            ('Mobile Phone', 40),          # Phone contract
            ('Internet', 45),              # Broadband
            ('Health & Fitness', 100),     # Gym, health products
            ('Personal Care', 50),         # Haircuts, toiletries
            ('Insurance', 100),            # Various insurances
            ('Travel', 200),               # Holiday savings
        ]

        created_count = 0
        for category_name, amount in budget_configs:
            try:
                category = expense_categories.get(category_name=category_name)

                existing = Budget.objects.filter(
                    user=user,
                    category=category,
                    start_date=month_start,
                    end_date=month_end
                ).exists()

                if not existing:
                    Budget.objects.create(
                        user=user,
                        category=category,
                        budget_name=f'{category_name} Budget',
                        budget_amount=Decimal(str(amount)),
                        period_type='monthly',
                        start_date=month_start,
                        end_date=month_end,
                        is_active=True
                    )
                    created_count += 1

            except Category.DoesNotExist:
                continue

        self.stdout.write(f'Budgets: {created_count} created')

    def _print_summary(self, user, token, password):
        """Print summary of seeded data"""
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(self.style.SUCCESS(
            f'UK SEEDING COMPLETE FOR: {user.username}'))
        self.stdout.write('=' * 60)

        self.stdout.write(f'\nCredentials:')
        self.stdout.write(f'  Username: {user.username}')
        self.stdout.write(f'  Password: {password}')
        self.stdout.write(f'  Email:    {user.email}')
        self.stdout.write(f'  Token:    {token.key}')

        self.stdout.write(f'\nData Summary:')
        self.stdout.write(
            f'  Categories:    {Category.objects.filter(user=user).count()}')
        self.stdout.write(
            f'  Bank Accounts: {BankAccount.objects.filter(user=user).count()}')
        self.stdout.write(
            f'  Transactions:  {Transaction.objects.filter(user=user).count()}')
        self.stdout.write(
            f'  Budgets:       {Budget.objects.filter(user=user, is_active=True).count()}')

        from django.db.models import Sum
        total_balance = BankAccount.objects.filter(
            user=user, is_active=True
        ).aggregate(total=Sum('current_balance'))['total'] or 0

        self.stdout.write(f'\nFinancial Summary:')
        self.stdout.write(f'  Total Balance: £{total_balance:,.2f}')

        self.stdout.write('\n' + '=' * 60)
        self.stdout.write('Example API calls:')
        self.stdout.write('=' * 60)
        self.stdout.write(f'''
# Login
curl -X POST https://budgetbox-api.onrender.com/api/auth/login/ \
  -H "Content-Type: application/json" \\
  -d '{{"username": "{user.username}", "password": "{password}"}}'

# Change password
curl -X POST https://budgetbox-api.onrender.com/api/auth/change-password/ \\
  -H "Authorization: Token {token.key}" \\
  -H "Content-Type: application/json" \\
  -d '{{"current_password": "{password}", "new_password": "newpassword456"}}'

# Get profile
curl https://budgetbox-api.onrender.com/api/auth/profile/ \\
  -H "Authorization: Token {token.key}"
''')
