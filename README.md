# BudgetBox API 💰

A robust Personal Finance Management REST API built with Django REST Framework, designed to help users track expenses, manage budgets, and gain insights into their financial health.

**🎯 Full-Stack Application**: This API powers a complete finance management system with a [React frontend](https://github.com/Vincent-Ngobeh/budgetbox-frontend) providing an intuitive user interface.

## 🌟 Features

### Core Functionality

- **Multi-Account Management**: Support for various account types (Current, Savings, ISA, Credit)
- **Transaction Tracking**: Comprehensive income/expense tracking with categorization
- **Budget Management**: Create and monitor budgets with real-time progress tracking
- **Financial Analytics**: Detailed statistics and spending insights
- **Multi-Currency Support**: GBP, USD, and EUR support

### Advanced Features

- **Smart Categorization**: Automatic transaction categorization with bulk operations
- **Budget Recommendations**: AI-powered budget suggestions based on spending patterns
- **Account Transfers**: Secure money transfers between accounts
- **Recurring Transactions**: Support for recurring income/expenses
- **Financial Reports**: Monthly summaries, account statements, and spending breakdowns

## 🚀 Tech Stack

### Backend

- **Framework**: Django 5.2.5 + Django REST Framework 3.16.1
- **Database**: PostgreSQL with optimized queries
- **Authentication**: Token-based authentication
- **Testing**: Pytest with 92% code coverage
- **Security**: CORS headers, environment-based configuration
- **Performance**: Redis caching, database query optimization

### Frontend ([Repository](https://github.com/Vincent-Ngobeh/budgetbox-frontend))

- **Framework**: React 18.2.0 with Material-UI
- **State Management**: React Context API
- **Routing**: React Router v6
- **Data Visualization**: Recharts
- **HTTP Client**: Axios

## 📋 Prerequisites

- Python 3.10+
- PostgreSQL 12+
- pip or pipenv

## 🛠️ Installation

### 1. Clone the Repository

```bash
git clone https://github.com/Vincent-Ngobeh/budgetbox-api.git
cd budgetbox-api
```

### 2. Set Up Virtual Environment

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create a `.env` file in the root directory:

```env
SECRET_KEY=your-secret-key-here
DEBUG=True
DB_NAME=budgetbox_db
DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_HOST=localhost
DB_PORT=5432
```

### 5. Set Up Database

```bash
# Create PostgreSQL database
createdb budgetbox_db

# Run migrations
python manage.py migrate

# Create superuser (optional)
python manage.py createsuperuser
```

### 6. Load Sample Data (Optional)

```bash
# Generate UK-specific demo data with realistic transactions
python manage.py create_uk_data --user testuser --accounts 3 --transactions 50

# Available test users (password: testpass123):
# - john_smith
# - sarah_jones
# - testuser
```

### 7. Run the Server

```bash
python manage.py runserver
```

The API will be available at `http://localhost:8000/`

### 8. Run the Frontend (Optional)

```bash
# In a new terminal, clone and run the frontend
git clone https://github.com/Vincent-Ngobeh/budgetbox-frontend.git
cd budgetbox-frontend
npm install
npm start
```

The frontend will be available at `http://localhost:3000/`

## 📚 API Documentation

### Interactive Testing

- **Postman Collection**: [View Collection](https://vincent-ngobeh-3663782.postman.co/workspace/Vincent-Ngobeh's-Workspace~952f4852-14ea-40b0-83fd-86c3984588b3/collection/48118241-9769c948-963a-40f1-abb1-b28ebe48aba1)
- **Environment Variables**: Pre-configured for local development
- **Sample Requests**: Complete examples for all endpoints

### Authentication Endpoints

| Method | Endpoint                    | Description       |
| ------ | --------------------------- | ----------------- |
| POST   | `/api/auth/register/`       | Register new user |
| POST   | `/api/auth/login/`          | Login user        |
| POST   | `/api/auth/logout/`         | Logout user       |
| GET    | `/api/auth/profile/`        | Get user profile  |
| PATCH  | `/api/auth/profile/update/` | Update profile    |

### Core Endpoints

#### Bank Accounts

| Method | Endpoint                        | Description               |
| ------ | ------------------------------- | ------------------------- |
| GET    | `/api/accounts/`                | List all accounts         |
| POST   | `/api/accounts/`                | Create new account        |
| GET    | `/api/accounts/{id}/`           | Get account details       |
| PUT    | `/api/accounts/{id}/`           | Update account            |
| DELETE | `/api/accounts/{id}/`           | Delete account            |
| GET    | `/api/accounts/summary/`        | Get accounts summary      |
| GET    | `/api/accounts/{id}/statement/` | Get account statement     |
| POST   | `/api/accounts/{id}/transfer/`  | Transfer between accounts |

#### Transactions

| Method | Endpoint                             | Description             |
| ------ | ------------------------------------ | ----------------------- |
| GET    | `/api/transactions/`                 | List transactions       |
| POST   | `/api/transactions/`                 | Create transaction      |
| GET    | `/api/transactions/{id}/`            | Get transaction details |
| PUT    | `/api/transactions/{id}/`            | Update transaction      |
| DELETE | `/api/transactions/{id}/`            | Delete transaction      |
| GET    | `/api/transactions/statistics/`      | Get statistics          |
| GET    | `/api/transactions/monthly_summary/` | Monthly summary         |
| POST   | `/api/transactions/bulk_categorize/` | Bulk categorize         |

#### Categories

| Method | Endpoint                        | Description               |
| ------ | ------------------------------- | ------------------------- |
| GET    | `/api/categories/`              | List categories           |
| POST   | `/api/categories/`              | Create category           |
| GET    | `/api/categories/{id}/usage/`   | Get usage stats           |
| POST   | `/api/categories/set_defaults/` | Create default categories |

#### Budgets

| Method | Endpoint                        | Description          |
| ------ | ------------------------------- | -------------------- |
| GET    | `/api/budgets/`                 | List budgets         |
| POST   | `/api/budgets/`                 | Create budget        |
| GET    | `/api/budgets/{id}/progress/`   | Get budget progress  |
| GET    | `/api/budgets/overview/`        | Get budgets overview |
| GET    | `/api/budgets/recommendations/` | Get recommendations  |
| POST   | `/api/budgets/{id}/clone/`      | Clone budget         |

### Query Parameters

#### Filtering Transactions

```
GET /api/transactions/?type=expense&date_from=2024-01-01&date_to=2024-12-31&min_amount=100
```

#### Filtering Accounts

```
GET /api/accounts/?type=current&is_active=true&currency=GBP
```

## 🧪 Testing

### Run Tests

```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=finance --cov-report=html

# View coverage report
# Open htmlcov/index.html in browser

# Run specific test file
pytest finance/tests/test_transactions.py

# Run with verbose output
pytest -v
```

### Test Coverage

The project maintains comprehensive test coverage including:

- Unit tests for models and serializers
- Integration tests for API endpoints
- Business logic validation tests
- Permission and authentication tests
- Edge case handling

**Current coverage: 92%**

### Testing with Sample Data

```bash
# Create test user with realistic UK data
python manage.py create_uk_data --user testuser --transactions 100

# Test credentials
# Username: testuser
# Password: testpass123
```

## 🔒 Security Features

- **Token Authentication**: Secure API access with token-based auth
- **User Isolation**: Complete data isolation between users
- **Input Validation**: Comprehensive validation on all inputs
- **SQL Injection Protection**: Django ORM prevents SQL injection
- **CORS Configuration**: Configurable CORS headers for frontend integration
- **Environment Variables**: Sensitive data stored in environment variables
- **Permission Classes**: Role-based access control

## 📊 Database Schema

The API uses a well-structured PostgreSQL database with the following main entities:

- **Users**: Authentication and user profiles
- **BankAccounts**: Multiple account types with currency support
- **Categories**: Income/expense categorization
- **Transactions**: Financial transactions with full audit trail
- **Budgets**: Budget planning and tracking

See the [Entity Relationship Diagram](docs/database/PersonalFinanceTrackerERDiagram.png) for detailed schema.

## 🚢 Deployment

### Docker Support (Coming Soon)

```dockerfile
# Dockerfile and docker-compose.yml to be added
```

### Production Considerations

- Use `gunicorn` or `uwsgi` as WSGI server
- Set `DEBUG=False` in production
- Configure proper database connection pooling
- Implement Redis for caching
- Use environment-specific settings files
- Set up proper logging
- Configure HTTPS/SSL

## 🤝 Contributing

This is a portfolio project, but suggestions and feedback are welcome!

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📈 Performance Optimizations

- **Database Query Optimization**: Using `select_related()` and `prefetch_related()`
- **Caching Strategy**: Redis caching for frequently accessed data
- **Pagination**: Default pagination for list endpoints
- **Bulk Operations**: Support for bulk create/update operations
- **Indexed Fields**: Database indexes on frequently queried fields

## 🎯 Project Highlights

### Complete Full-Stack Application

- **Backend**: Production-ready Django REST API with 92% test coverage
- **Frontend**: React SPA with Material-UI and data visualization
- **Testing**: Comprehensive test suite + Postman collection
- **Documentation**: Detailed API docs and setup guides
- **Sample Data**: Realistic UK financial data generator

### Key Achievements

- ✅ Clean architecture with separation of concerns
- ✅ Comprehensive error handling and validation
- ✅ Security best practices implementation
- ✅ Optimized database queries with caching
- ✅ Full CRUD operations for all resources
- ✅ Advanced features (bulk operations, transfers, cloning)
- ✅ Responsive frontend with modern UI/UX

## 📝 API Usage Examples

### Using Postman Collection

Import the [Postman Collection](https://vincent-ngobeh-3663782.postman.co/workspace/Vincent-Ngobeh's-Workspace~952f4852-14ea-40b0-83fd-86c3984588b3/collection/48118241-9769c948-963a-40f1-abb1-b28ebe48aba1) for ready-to-use requests with:

- Pre-configured environment variables
- Authentication token management
- Sample request bodies
- Complete endpoint coverage

### Quick Test Flow

```bash
# 1. Start the backend
python manage.py runserver

# 2. Create test data
python manage.py create_uk_data --user john_smith

# 3. Test via Postman or cURL
# Login (returns auth token)
curl -X POST http://localhost:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username": "john_smith", "password": "testpass123"}'

# 4. Or use the frontend
cd ../budgetbox-frontend
npm start
# Login with john_smith / testpass123
```

### Sample API Calls

### Register a New User

```bash
curl -X POST http://localhost:8000/api/auth/register/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "johndoe",
    "email": "john@example.com",
    "password": "securepass123",
    "first_name": "John",
    "last_name": "Doe"
  }'
```

### Create a Transaction

```bash
curl -X POST http://localhost:8000/api/transactions/ \
  -H "Authorization: Token your-auth-token" \
  -H "Content-Type: application/json" \
  -d '{
    "bank_account": "account-uuid",
    "category": "category-uuid",
    "transaction_description": "Grocery Shopping",
    "transaction_type": "expense",
    "transaction_amount": "45.50",
    "transaction_date": "2024-01-15"
  }'
```

### Get Budget Progress

```bash
curl -X GET http://localhost:8000/api/budgets/{budget-id}/progress/ \
  -H "Authorization: Token your-auth-token"
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 👤 Author

**Vincent Sam Ngobeh**

- GitHub: [@Vincent-Ngobeh](https://github.com/Vincent-Ngobeh)
- LinkedIn: [Vincent Ngobeh](https://www.linkedin.com/in/vincent-ngobeh/)
- Email: vincentngobeh@gmail.com
- Portfolio: [View Live Projects](https://github.com/Vincent-Ngobeh)

## 🙏 Acknowledgments

- Django REST Framework documentation and community
- PostgreSQL for robust database management
- The Python community for excellent packages
- Stack Overflow for problem-solving support

---

**Note**: This is a portfolio project demonstrating proficiency in Django REST Framework, API design, database management, and software engineering best practices. The codebase emphasizes clean architecture, comprehensive testing, and production-ready features.
