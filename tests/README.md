# ChurchTools API Tests

This directory contains unit tests for the ChurchTools API application.

## Test Execution

### Local Execution

#### For Linux/Windows:

To run the tests locally, use the following command:

```bash
# Install dependencies
pip install -r requirements.txt

# Run the tests
python -m pytest tests/
```

#### For macOS:

macOS users may encounter issues with the reportlab installation. Here are three approaches:

**Option 1: Use the installation script (recommended)**

```bash
# Make the script executable
chmod +x install-macos.sh

# Run the installation script
./install-macos.sh

# Activate the virtual environment (if not already activated)
source venv/bin/activate

# Run the tests
python -m pytest tests/
```

**Option 2: Manual installation**

```bash
# Create a virtual environment
python -m venv venv
source venv/bin/activate

# Install reportlab without C extensions
pip install --no-binary=reportlab reportlab==3.5.68

# Install the remaining dependencies
pip install -r requirements-macos.txt

# Run the tests
python -m pytest tests/
```

**Option 3: Use Docker**

```bash
# Build the Docker image
docker build -t churchtools-api:test .

# Run the tests in the container
docker run --rm churchtools-api:test python -m pytest tests/
```

### Running with Code Coverage Report

To run the tests with a code coverage report:

```bash
python -m pytest --cov=app tests/ --cov-report=term
```

For an HTML report:

```bash
python -m pytest --cov=app tests/ --cov-report=html
```

### IntelliJ Run Configurations

Two IntelliJ Run configurations have been created:

1. **Run Tests with Coverage**: Runs all tests and displays a code coverage report in the terminal
2. **Run Tests with HTML Coverage**: Runs all tests and generates an HTML code coverage report

## Test Structure

The tests are divided into the following categories:

1. **Utils Tests**: Test helper functions with 97% code coverage
2. **Database Tests**: Test database operations with 84% code coverage
3. **Auth Tests**: Test authentication functions with 43% code coverage
4. **Appointments Tests**: Test appointment management functions with 23% code coverage
5. **PDF Generator Tests**: Test PDF creation functions with 82% code coverage

The total code coverage is 51%.

## CI/CD Pipeline

The tests are automatically run in the GitHub Actions pipeline. There are two workflows:

1. **test-and-build.yml**: Runs on every push and pull request
   - Runs all tests with code coverage report
   - Uploads the code coverage report to Codecov
   - Builds the Docker image (without pushing)

2. **release.yml**: Only runs manually via the GitHub Actions UI
   - Requires entering a version (e.g., v1.0.0)
   - Runs all tests with code coverage report
   - Uploads the code coverage report to Codecov
   - Builds the Docker image and pushes it to the GitHub Container Registry (GHCR)
   - Tags the image with the specified version and "latest"