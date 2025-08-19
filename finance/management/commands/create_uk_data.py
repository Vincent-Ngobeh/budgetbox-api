from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from faker import Faker
from finance.models import BankAccount, Category, Transaction, Budget
from decimal import Decimal
import random
from datetime import date, timedelta

class Command(BaseCommand):
    help = 'Generate UK dummy financial data'
    
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
            default=20,
            help='Number of transactions to create'
        )
    
    def handle(self, *args, **options):
        # Get or create a test user
        user, created = User.objects.get_or_create(
            username='testuser',
            defaults={
                'first_name': self.fake.first_name(),
                'last_name': self.fake.last_name(),
                'email': f"{self.fake.user_name()}@{self.fake.random_element(['gmail.com', 'outlook.com', 'yahoo.co.uk'])}"
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
            ('Salary', 'income'),
            ('Freelance', 'income'),
            ('Benefits', 'income'),
            ('Groceries', 'expense'),
            ('Transport', 'expense'),
            ('Council Tax', 'expense'),
            ('Utilities', 'expense'),
            ('Mobile Phone', 'expense'),
            ('Entertainment', 'expense'),
            ('Rent/Mortgage', 'expense'),
            ('Insurance', 'expense'),
            ('Eating Out', 'expense'),
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
        """Create realistic UK bank accounts"""
        uk_banks = [
            'Barclays', 'HSBC', 'Lloyds Banking Group', 
            'Santander UK', 'NatWest', 'TSB Bank'
        ]
        
        account_names = [
            'Main Current Account', 'Savings Account', 'Emergency Fund',
            'Holiday Savings', 'ISA Account', 'Credit Card'
        ]
        
        account_types = ['current', 'savings', 'isa', 'credit']
        
        for i in range(count):
            account_type = random.choice(account_types)
            
            # Balance based on account type
            if account_type == 'credit':
                balance = self.fake.pydecimal(
                    left_digits=4, right_digits=2, positive=False,
                    min_value=-2000, max_value=0
                )
            elif account_type == 'savings':
                balance = self.fake.pydecimal(
                    left_digits=5, right_digits=2, positive=True,
                    min_value=1000, max_value=25000
                )
            else:  # current, isa
                balance = self.fake.pydecimal(
                    left_digits=4, right_digits=2, positive=True,
                    min_value=100, max_value=8000
                )
            
            BankAccount.objects.create(
                user=user,
                account_name=random.choice(account_names),
                account_type=account_type,
                bank_name=random.choice(uk_banks),
                account_number_masked=f"****{self.fake.random_int(min=1000, max=9999)}",
                currency='GBP',
                current_balance=balance,
                is_active=True
            )
        
        self.stdout.write(f'Created {count} UK bank accounts')
    
    def create_uk_transactions(self, user, count):
        """Create UK transactions"""
        accounts = BankAccount.objects.filter(user=user)
        categories = Category.objects.filter(user=user)
        
        if not accounts.exists() or not categories.exists():
            self.stdout.write('No accounts or categories found')
            return
        
        uk_descriptions = {
            'expense': [
                'Tesco Stores', 'Sainsbury\'s Supermarket', 'ASDA', 'Morrison\'s',
                'TfL Travel Charge', 'Uber Trip', 'Shell Petrol Station',
                'Amazon UK Purchase', 'Netflix Subscription', 'Spotify Premium',
                'Council Tax Payment', 'British Gas Bill', 'Thames Water',
                'EE Mobile', 'Sky Broadband', 'John Lewis', 'Marks & Spencer',
                'Costa Coffee', 'Pret A Manger', 'McDonald\'s UK'
            ],
            'income': [
                'Monthly Salary', 'Freelance Payment', 'Pension Payment',
                'Universal Credit', 'Child Benefit', 'Tax Refund',
                'Bonus Payment', 'Dividend Payment'
            ]
        }
        
        for i in range(count):
            account = random.choice(accounts)
            category = random.choice(categories)
            
            # Match transaction type to category type
            transaction_type = category.category_type
            
            # Amounts based on category
            if category.category_name == 'Salary':
                amount = self.fake.pydecimal(
                    left_digits=4, right_digits=2, positive=True,
                    min_value=2000, max_value=6000
                )
            elif category.category_name in ['Groceries', 'Eating Out']:
                amount = self.fake.pydecimal(
                    left_digits=3, right_digits=2, positive=True,
                    min_value=5, max_value=150
                )
            elif category.category_name in ['Rent/Mortgage', 'Council Tax']:
                amount = self.fake.pydecimal(
                    left_digits=4, right_digits=2, positive=True,
                    min_value=800, max_value=2500
                )
            else:
                amount = self.fake.pydecimal(
                    left_digits=3, right_digits=2, positive=True,
                    min_value=10, max_value=500
                )
            
            # Make expenses negative
            if transaction_type == 'expense':
                amount = -amount
            
            Transaction.objects.create(
                user=user,
                bank_account=account,
                category=category,
                transaction_description=random.choice(uk_descriptions[transaction_type]),
                transaction_type=transaction_type,
                transaction_amount=amount,
                transaction_date=self.fake.date_between(start_date='-3m', end_date='today'),
                transaction_note=self.fake.text(max_nb_chars=100) if random.choice([True, False]) else None,
                reference_number=f"REF{self.fake.random_int(min=100000, max=999999)}" if random.choice([True, False]) else None,
                is_recurring=random.choice([True, False])
            )
        
        self.stdout.write(f'Created {count} UK transactions')
    
    def create_uk_budgets(self, user):
        """Create UK budgets"""
        expense_categories = Category.objects.filter(user=user, category_type='expense')
        
        if not expense_categories.exists():
            return
        
        budget_data = [
            ('Monthly Groceries', 'Groceries', 400),
            ('Monthly Transport', 'Transport', 150),
            ('Monthly Entertainment', 'Entertainment', 200),
            ('Monthly Utilities', 'Utilities', 180),
        ]
        
        for budget_name, category_name, amount in budget_data:
            try:
                category = expense_categories.get(category_name=category_name)
                Budget.objects.create(
                    user=user,
                    category=category,
                    budget_name=budget_name,
                    budget_amount=Decimal(str(amount)),
                    budget_type='monthly',
                    period_type='monthly',
                    start_date=date.today().replace(day=1),
                    end_date=date.today().replace(day=1) + timedelta(days=32),
                    is_active=True
                )
            except Category.DoesNotExist:
                continue
        
        self.stdout.write('Created UK budgets')