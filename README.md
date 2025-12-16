# CA AI MVP

<div align="center">
  <img src="ca_ai/hero_img.png" alt="CA AI MVP" width="600">
</div>

A local-first, privacy-preserving application for Chartered Accountants to manage GST compliance with AI assistance.

## Architecture

This is a monorepo containing:

- **frontend/**: Tauri 2.0 + React 19 + TypeScript 5.5 desktop application
- **backend/**: Python 3.12+ + FastAPI 0.115+ local processing engine
- **server/**: Rules server (PostgreSQL + FastAPI) for GST rules management
- **shared/**: Shared TypeScript type definitions

## Core Principle

**Documents never leave user's machine. LLM sees only summaries (Cursor-style architecture).**

## Getting Started

### Prerequisites

- Node.js 20+ and Yarn
- Python 3.12+
- PostgreSQL 16+ (for rules server)
- Rust (for Tauri)

### Setup

1. **Backend Setup**

   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Frontend Setup**

   ```bash
   cd frontend
   yarn install
   ```

3. **Rules Server Setup**

   ```bash
   cd server
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

4. **Shared Types**
   ```bash
   cd shared
   yarn install
   ```

## Development

See `ENGINEER_TDR.md` for detailed architecture and implementation plan.

## Roadmap & Todos

### High Priority

- [ ] **Testing Suite**

  - [ ] Unit tests for rules engine
  - [ ] Unit tests for OCR pipeline
  - [ ] Unit tests for context firewall
  - [ ] Integration tests for end-to-end workflows
  - [ ] API endpoint tests
  - [ ] Database migration tests

- [ ] **Performance Optimization**

  - [ ] Profiling and bottleneck identification
  - [ ] Memory leak detection and fixes
  - [ ] Database query optimization
  - [ ] Load testing with large document sets
  - [ ] Concurrent user stress testing

- [ ] **Documentation**
  - [ ] User FAQ
  - [ ] API documentation
  - [ ] Distribution and packaging guide
  - [ ] Update mechanism implementation

### Medium Priority

- [ ] **Beta Testing**

  - [ ] Recruit beta CA testers
  - [ ] Feedback collection system
  - [ ] Bug tracking and prioritization

- [ ] **Feature Enhancements**
  - [ ] Advanced OCR accuracy improvements
  - [ ] Additional GST rule implementations
  - [ ] Enhanced reconciliation algorithms
  - [ ] Export format improvements

### Community Contributions Welcome

We welcome contributions in the following areas:

- [ ] **GST Rules**

  - [ ] Additional GST rule implementations
  - [ ] Rule accuracy improvements
  - [ ] Rule documentation and citations

- [ ] **OCR Improvements**

  - [ ] Better handling of Indian invoice formats
  - [ ] Multi-language support (Hindi, regional languages)
  - [ ] Table extraction improvements

- [ ] **UI/UX Enhancements**

  - [ ] Accessibility improvements
  - [ ] Dark mode support
  - [ ] Keyboard shortcuts
  - [ ] Better error messages

- [ ] **Documentation**

  - [ ] Tutorial videos
  - [ ] Use case examples
  - [ ] Best practices guide

- [ ] **Testing**

  - [ ] Test case additions
  - [ ] Test data sets
  - [ ] Performance benchmarks

- [ ] **Localization**
  - [ ] Hindi translation
  - [ ] Regional language support

## Contributing

We welcome contributions from the community! This project is open source and we appreciate your help in making it better.

### How to Contribute

1. **Fork the Repository**

   - Click the "Fork" button on GitHub
   - Clone your fork locally

2. **Create a Branch**

   ```bash
   git checkout -b feature/your-feature-name
   # or
   git checkout -b fix/your-bug-fix
   ```

3. **Make Your Changes**

   - Follow the existing code style
   - Write clear commit messages
   - Add tests if applicable
   - Update documentation as needed

4. **Test Your Changes**

   - Run existing tests: `yarn test` (frontend) or `pytest` (backend)
   - Ensure all tests pass
   - Test manually if applicable

5. **Submit a Pull Request**
   - Push your branch to your fork
   - Open a Pull Request on GitHub
   - Fill out the PR template with:
     - Description of changes
     - Related issues (if any)
     - Testing performed
     - Screenshots (for UI changes)

### Development Guidelines

#### Code Style

- **Frontend**: Follow TypeScript best practices, use ESLint/Prettier
- **Backend**: Follow PEP 8, use `ruff` for linting
- **Commits**: Use conventional commits format:
  - `feat:` for new features
  - `fix:` for bug fixes
  - `docs:` for documentation
  - `test:` for tests
  - `refactor:` for refactoring
  - `chore:` for maintenance

#### Project Structure

- Keep changes focused and minimal
- Maintain backward compatibility when possible
- Update relevant documentation
- Add tests for new features

#### Pull Request Process

1. Ensure your code passes all CI checks
2. Request review from maintainers
3. Address review feedback
4. Once approved, maintainers will merge

### Areas Where We Need Help

- **GST Rules Expertise**: Help us implement and verify GST rules accuracy
- **OCR Improvements**: Better handling of Indian document formats
- **Testing**: More comprehensive test coverage
- **Documentation**: User guides, tutorials, examples
- **Localization**: Translations for regional languages
- **Performance**: Optimization suggestions and improvements

### Questions?

- Open an issue for bug reports or feature requests
- Start a discussion for questions or ideas
- Check `ENGINEER_TDR.md` for architecture details

### Code of Conduct

- Be respectful and inclusive
- Welcome newcomers and help them get started
- Focus on constructive feedback
- Respect different viewpoints and experiences

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
