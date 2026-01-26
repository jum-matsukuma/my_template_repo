---
name: development
description: Core software development skills including architecture patterns, programming languages, and development tools. Provides background knowledge for general software engineering tasks.
user-invocable: false
---

# Software Development Skills

Core software development capabilities including architecture patterns, programming language expertise, and development tools.

## Available Resources

- [architecture-patterns.md](architecture-patterns.md) - Software architecture and design patterns
- [programming-languages.md](programming-languages.md) - Language-specific skills and best practices
- [development-tools.md](development-tools.md) - Build tools, testing frameworks, and DevOps

## Quick Reference

### Architecture Patterns
- **Layered Architecture**: Presentation, business logic, data access layers
- **Component-Based**: Modular, reusable components with composition
- **Microservices**: Service decomposition, API gateway, service discovery
- **Clean Architecture**: Dependency inversion, use case driven design

### Design Patterns
- **Creational**: Factory, Builder, Singleton, Dependency Injection
- **Behavioral**: Observer, Strategy, Command, State
- **Structural**: Adapter, Decorator, Facade, Repository

### API Design
- **RESTful**: Resource-oriented, HTTP semantics, pagination
- **GraphQL**: Schema-first, query optimization, subscriptions
- **Event-Driven**: Event sourcing, CQRS, message queues

## Development Workflow

1. **Use ES modules** (import/export) syntax, not CommonJS (require)
2. **Destructure imports** when possible
3. **Follow language-specific formatting** (Prettier, Black, rustfmt)
4. **Use strict TypeScript** configuration when applicable
5. **Prefer composition** over inheritance
