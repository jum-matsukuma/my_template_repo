---
name: templates
description: Skill templates for creating project-specific skills. Copy these templates to create new skills customized for your project.
user-invocable: false
---

# Skill Templates

Templates for creating project-specific skills. Use these as starting points when setting up new projects.

## Available Templates

- [project-domain.md](project-domain.md) - Domain knowledge and business rules
- [technology-stack.md](technology-stack.md) - Technology choices and configurations
- [team-conventions.md](team-conventions.md) - Team coding standards and workflows
- [custom-tools.md](custom-tools.md) - Project-specific tools and utilities

## Usage

1. Copy the appropriate template to a new skill directory:
   ```bash
   mkdir -p .claude/skills/my-project
   cp .claude/skills/templates/project-domain.md .claude/skills/my-project/domain.md
   ```

2. Create a `SKILL.md` with proper frontmatter:
   ```yaml
   ---
   name: my-project
   description: Project-specific skills for [project name]
   ---

   # My Project Skills

   ## Resources
   - [domain.md](domain.md) - Domain knowledge
   ```

3. Customize the copied template with your project details
