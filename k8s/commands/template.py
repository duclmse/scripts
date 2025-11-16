
"""Resource templates manager"""
from core.decorators import Command, arg
from core.logger import Logger
from core.config import KubeConfig
from pathlib import Path

@Command.register("template", help="Manage resource templates", args=[
    arg("action", choices=["save", "list", "use", "delete"], help="Action"),
    arg("name", nargs="?", help="Template name"),
    arg("--file", help="Template file"),
    arg("--vars", help="Variables as JSON"),
])
class TemplateCommand:
    """Create and use resource templates"""
    
    def __init__(self, kube):
        self.kube = kube
        self.config = KubeConfig()
    
    def execute(self, args):
        if args.action == "save":
            self.save_template(args)
        elif args.action == "list":
            self.list_templates()
        elif args.action == "use":
            self.use_template(args)
        elif args.action == "delete":
            self.delete_template(args.name)
    
    def save_template(self, args):
        """Save a template"""
        if not args.name or not args.file:
            Logger.error("Name and file required")
            return
        
        filepath = Path(args.file)
        if not filepath.exists():
            Logger.error(f"File not found: {args.file}")
            return
        
        templates = self.config.get_templates()
        templates[args.name] = {
            "content": filepath.read_text(),
            "description": f"Template saved from {args.file}"
        }
        self.config.save_templates(templates)
        Logger.success(f"Template saved: {args.name}")
    
    def list_templates(self):
        """List all templates"""
        templates = self.config.get_templates()
        
        if not templates:
            print("No templates saved")
            return
        
        print(f"{'NAME':<20} {'DESCRIPTION':<50}")
        print("-" * 70)
        for name, data in templates.items():
            desc = data.get('description', 'No description')
            print(f"{name:<20} {desc:<50}")
    
    def use_template(self, args):
        """Apply a template"""
        if not args.name:
            Logger.error("Template name required")
            return
        
        templates = self.config.get_templates()
        
        if args.name not in templates:
            Logger.error(f"Template '{args.name}' not found")
            return
        
        template_content = templates[args.name]['content']
        
        # Replace variables if provided
        if args.vars:
            import json
            variables = json.loads(args.vars)
            for key, value in variables.items():
                template_content = template_content.replace(f"{{{key}}}", value)
        
        # Save to temp file and apply
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(template_content)
            temp_file = f.name
        
        try:
            self.kube.run(["apply", "-f", temp_file, "-n", self.kube.namespace], 
                         capture_output=False)
            Logger.success(f"Applied template: {args.name}")
        finally:
            Path(temp_file).unlink()
    
    def delete_template(self, name):
        """Delete a template"""
        if not name:
            Logger.error("Template name required")
            return
        
        templates = self.config.get_templates()
        
        if name in templates:
            del templates[name]
            self.config.save_templates(templates)
            Logger.success(f"Deleted template: {name}")
        else:
            Logger.error(f"Template '{name}' not found")
