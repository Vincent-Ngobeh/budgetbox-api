from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from faker import Faker
from finance.models import BankAccount, Category, Transaction, Budget
from decimal import Decimal
import random
from datetime import date, timedelta


class Command(BaseCommand):
    help = 'Generate UK dummy financial data with London ranges'

    def __init__(self):
        super().__init__()
        self.fake = Faker('en_GB')  # UK locale

    def add_arguments(self, parser):
        parser.add_argument(
            '--accounts',
            type=int,
            default=3,
            help='Number of bank accounts to create'
        )
        parser.add_argument(
            '--transactions',
            type=int,
            default=50,  # Increased for more data
            help='Number of transactions to create'
        )
        parser.add_argument(
            '--user',
            type=str,
            default='john_smith',
            help='Username to create data for (john_smith, sarah_jones, or testuser)'
        )

    def handle(self, *args, **options):
        # Create multiple test users with proper data
        test_users = [
            {
                'username': 'john_smith',
                'first_name': 'John',
                'last_name': 'Smith',
                'email': 'john.smith@gmail.com'
            },
            {
                'username': 'sarah_jones',
                'first_name': 'Sarah',
                'last_name': 'Jones',
                'email': 'sarah.jones@outlook.com'
            },
            {
                'username': 'testuser',
                'first_name': 'Test',
                'last_name': 'User',
                'email': 'testuser@example.com'
            }
        ]

        # Find the requested user data
        username = options.get('user', 'john_smith')
        user_data = next(
            (u for u in test_users if u['username'] == username), test_users[0])

        user, created = User.objects.get_or_create(
            username=user_data['username'],
            defaults={
                'first_name': user_data['first_name'],
                'last_name': user_data['last_name'],
                'email': user_data['email']
            }
        )

        if created:
            user.set_password('testpass123')
            user.save()
            self.stdout.write(f'Created test user: {user.username}')

        # Create categories first
        self.create_uk_categories(user)

        # Create bank accounts
        self.create_uk_bank_accounts(user, options['accounts'])

        # Create transactions
        self.create_uk_transactions(user, options['transactions'])

        # Create budgets
        self.create_uk_budgets(user)

        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully created UK dummy data for {user.username}'
            )
        )

    def create_uk_categories(self, user):
        """Create UK financial categories"""
        uk_categories = [
            # Income categories
            ('Salary', 'income'),
            ('Freelance', 'income'),
            ('Benefits', 'income'),
            ('Investment Income', 'income'),
            ('Bonus', 'income'),

            # Essential expenses
            ('Rent/Mortgage', 'expense'),
            ('Council Tax', 'expense'),
            ('Groceries', 'expense'),
            ('Utilities', 'expense'),
            ('Insurance', 'expense'),

            # Transport
            ('Transport', 'expense'),
            ('TfL/Oyster', 'expense'),
            ('Petrol', 'expense'),

            # Subscriptions & Services
            ('Mobile Phone', 'expense'),
            ('Internet', 'expense'),
            ('Subscriptions', 'expense'),

            # Lifestyle
            ('Eating Out', 'expense'),
            ('Entertainment', 'expense'),
            ('Shopping', 'expense'),
            ('Health & Fitness', 'expense'),
            ('Personal Care', 'expense'),
        ]

        for name, cat_type in uk_categories:
            Category.objects.get_or_create(
                user=user,
                category_name=name,
                category_type=cat_type,
                defaults={'is_default': True}
            )

        self.stdout.write('Created UK categories')

    def create_uk_bank_accounts(self, user, count):
        """Create UK bank accounts"""
        uk_banks = [
            'Barclays', 'HSBC', 'Lloyds Banking Group',
            'Santander UK', 'NatWest', 'TSB Bank',
            'Nationwide', 'Metro Bank', 'Monzo', 'Starling Bank'
        ]

        account_configs = [
            # Typical current account
            ('Main Current Account', 'current', 500, 5000),
            ('Savings Account', 'savings', 5000,
             25000),      # Emergency fund range
            ('ISA Account', 'isa', 1000, 20000),              # ISA savings
            ('Holiday Savings', 'savings', 500, 5000),        # Goal-based savings
            ('Credit Card', 'credit', -3000, -100),           # Credit card debt
        ]

        created_accounts = []
        for i in range(min(count, len(account_configs))):
            name, acc_type, min_bal, max_bal = account_configs[i]

            balance = Decimal(str(random.uniform(min_bal, max_bal))).quantize(
                Decimal('0.01'))

            # Generate UK account number format (****1234)
            last_four = str(random.randint(1000, 9999))

            account = BankAccount.objects.create(
                user=user,
                account_name=name,
                account_type=acc_type,
                bank_name=random.choice(uk_banks),
                account_number_masked=f"****{last_four}",
                currency='GBP',
                current_balance=balance,
                is_active=True
            )
            created_accounts.append(account)

        self.stdout.write(f'Created {len(created_accounts)} UK bank accounts')

    def create_uk_transactions(self, user, count):
        """Create UK transactions with London amounts"""
        accounts = BankAccount.objects.filter(user=user)
        categories = Category.objects.filter(user=user)

        if not accounts.exists() or not categories.exists():
            self.stdout.write('No accounts or categories found')
            return

        # London transaction descriptions and amounts
        transaction_templates = {
            'Salary': {
                'descriptions': ['Monthly Salary Payment', 'Salary - EMPLOYER NAME'],
                'amount_range': (2500, 4500),  # London median salary range
                'frequency': 'monthly'
            },
            'Freelance': {
                'descriptions': ['Freelance Project Payment', 'Invoice Payment - Client'],
                'amount_range': (300, 2000),
                'frequency': 'occasional'
            },
            'Rent/Mortgage': {
                'descriptions': ['Monthly Rent Payment', 'Mortgage Payment - Halifax'],
                'amount_range': (1200, 2500),  # London rent/mortgage
                'frequency': 'monthly'
            },
            'Council Tax': {
                'descriptions': ['Council Tax - Wandsworth', 'Council Tax Payment'],
                'amount_range': (120, 200),  # London council tax
                'frequency': 'monthly'
            },
            'Groceries': {
                'descriptions': [
                    'Tesco Express', 'Sainsbury\'s Local', 'ASDA Superstore',
                    'Waitrose & Partners', 'M&S Food', 'Lidl GB', 'ALDI',
                    'Co-op Food', 'Iceland'
                ],
                'amount_range': (15, 120),  # Weekly shopping varies
                'frequency': 'weekly'
            },
            'Transport': {
                'descriptions': [
                    'TfL Travel - Zone 1-3', 'Uber Trip', 'Bolt Ride',
                    'Santander Cycles', 'National Rail', 'Citymapper PASS'
                ],
                'amount_range': (3, 40),  # Single trips to daily caps
                'frequency': 'frequent'
            },
            'TfL/Oyster': {
                'descriptions': ['TfL Auto Top-up', 'Oyster Card Top-up', 'Monthly Travelcard'],
                'amount_range': (150, 250),  # Monthly London travel
                'frequency': 'monthly'
            },
            'Utilities': {
                'descriptions': [
                    'British Gas - Energy Bill', 'Thames Water', 'EDF Energy',
                    'Octopus Energy', 'Bulb Energy'
                ],
                'amount_range': (80, 200),  # Combined utilities
                'frequency': 'monthly'
            },
            'Mobile Phone': {
                'descriptions': ['EE Mobile', 'O2 Mobile', 'Three Mobile', 'Vodafone UK'],
                'amount_range': (15, 50),  # Phone contracts
                'frequency': 'monthly'
            },
            'Internet': {
                'descriptions': ['BT Broadband', 'Virgin Media', 'Sky Broadband', 'TalkTalk'],
                'amount_range': (25, 60),  # Broadband packages
                'frequency': 'monthly'
            },
            'Subscriptions': {
                'descriptions': [
                    'Netflix', 'Spotify Premium', 'Amazon Prime',
                    'Disney+', 'Apple Music', 'Gym Membership - PureGym',
                    'The Times Digital', 'PlayStation Plus'
                ],
                'amount_range': (5.99, 49.99),  # Various subscriptions
                'frequency': 'monthly'
            },
            'Eating Out': {
                'descriptions': [
                    'Pret A Manger', 'Costa Coffee', 'Nando\'s',
                    'Wagamama', 'Pizza Express', 'Dishoom',
                    'Five Guys', 'Leon', 'Honest Burgers',
                    'Starbucks', 'Greggs', 'McDonald\'s'
                ],
                'amount_range': (4, 85),  # Coffee to dinner
                'frequency': 'frequent'
            },
            'Entertainment': {
                'descriptions': [
                    'Vue Cinema', 'Odeon Leicester Square', 'National Theatre',
                    'O2 Arena', 'Steam Purchase', 'Apple App Store',
                    'Ticketmaster', 'London Zoo', 'British Museum Donation'
                ],
                'amount_range': (5, 120),  # Various entertainment
                'frequency': 'occasional'
            },
            'Shopping': {
                'descriptions': [
                    'Amazon UK', 'John Lewis', 'Marks & Spencer',
                    'Primark Oxford Street', 'IKEA Wembley', 'Argos',
                    'Next', 'H&M', 'Uniqlo', 'Boots', 'Superdrug'
                ],
                'amount_range': (10, 250),  # Various shopping
                'frequency': 'occasional'
            },
            'Petrol': {
                'descriptions': ['Shell Petrol Station', 'BP Garage', 'Esso', 'Tesco Petrol'],
                'amount_range': (40, 80),  # Tank fill-up
                'frequency': 'occasional'
            },
            'Insurance': {
                'descriptions': ['Aviva Home Insurance', 'Direct Line Car Insurance', 'Vitality Health'],
                'amount_range': (25, 150),  # Various insurances
                'frequency': 'monthly'
            },
            'Health & Fitness': {
                'descriptions': ['Boots Pharmacy', 'Holland & Barrett', 'GymBox', 'Barry\'s Bootcamp'],
                'amount_range': (10, 150),  # Health purchases to gym
                'frequency': 'occasional'
            }
        }

        # Generate transactions over the last 3 months
        start_date = date.today() - timedelta(days=90)

        for i in range(count):
            # Pick a random category
            category = random.choice(categories)

            # Skip if we don't have a template for this category
            if category.category_name not in transaction_templates:
                continue

            template = transaction_templates[category.category_name]

            # Generate transaction details
            description = random.choice(template['descriptions'])
            min_amount, max_amount = template['amount_range']
            amount = Decimal(str(random.uniform(min_amount, max_amount))).quantize(
                Decimal('0.01'))

            # Make expenses negative
            if category.category_type == 'expense':
                amount = -amount

            # Random date in the last 3 months
            trans_date = self.fake.date_between(
                start_date=start_date, end_date='today')

            # Select account (prefer current account for most transactions)
            current_accounts = accounts.filter(account_type='current')
            if current_accounts.exists() and random.random() < 0.8:
                account = random.choice(current_accounts)
            else:
                account = random.choice(accounts)

            # Determine if recurring (monthly bills are often recurring)
            is_recurring = template['frequency'] == 'monthly' and random.random(
            ) < 0.7

            Transaction.objects.create(
                user=user,
                bank_account=account,
                category=category,
                transaction_description=description,
                transaction_type=category.category_type,
                transaction_amount=amount,
                transaction_date=trans_date,
                transaction_note=self.fake.text(
                    max_nb_chars=50) if random.random() < 0.3 else None,
                reference_number=f"REF{self.fake.random_int(min=100000, max=999999)}" if random.random(
                ) < 0.5 else None,
                is_recurring=is_recurring
            )

        self.stdout.write(f'Created {count} UK transactions')

    def create_uk_budgets(self, user):
        """Create London budgets"""
        expense_categories = Category.objects.filter(
            user=user, category_type='expense')

        if not expense_categories.exists():
            return

        # London monthly budgets
        budget_data = [
            ('Monthly Rent', 'Rent/Mortgage', 1800),      # London average rent
            # £100/week for groceries
            ('Monthly Groceries', 'Groceries', 400),
            ('Monthly Transport', 'Transport', 200),       # Zone 1-3 travelcard
            ('Monthly Eating Out', 'Eating Out', 250),    # Social dining budget
            # Cinema, events, etc.
            ('Monthly Entertainment', 'Entertainment', 150),
            ('Monthly Utilities', 'Utilities', 150),       # Gas, electric, water
            ('Monthly Subscriptions', 'Subscriptions', 75),  # Various subscriptions
            ('Council Tax', 'Council Tax', 150),           # Band D average
        ]

        for budget_name, category_name, amount in budget_data:
            try:
                category = expense_categories.get(category_name=category_name)
                Budget.objects.create(
                    user=user,
                    category=category,
                    budget_name=budget_name,
                    budget_amount=Decimal(str(amount)),
                    period_type='monthly',
                    start_date=date.today().replace(day=1),
                    end_date=(date.today().replace(
                        day=1) + timedelta(days=32)).replace(day=1) - timedelta(days=1),
                    is_active=True
                )
            except Category.DoesNotExist:
                continue

        self.stdout.write('Created London budgets')
