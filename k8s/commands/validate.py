
"""Kubernetes manifest validator"""
import yaml
from pathlib import Path
from core.decorators import Command, arg
from core.logger import Logger
from core.colors import Colors

@Command.register("validate", help="Validate Kubernetes manifests", args=[
    arg("file", help="YAML file to validate"),
    arg("--security", action="store_true", help="Check security best practices"),
    arg("--schema", action="store_true", help="Validate against K8s schema"),
])
class ValidateCommand:
    """Validate YAML before applying"""
    
    def __init__(self, kube):
        self.kube = kube
        self.errors = []
        self.warnings = []
    
    def execute(self, args):
        filepath = Path(args.file)
        
        if not filepath.exists():
            Logger.error(f"File not found: {args.file}")
            return
        
        Logger.info(f"Validating {args.file}...")
        
        # Parse YAML
        try:
            with open(filepath) as f:
                docs = list(yaml.safe_load_all(f))
        except yaml.YAMLError as e:
            Logger.error(f"YAML syntax error: {e}")
            return
        
        # Validate each document
        for i, doc in enumerate(docs, 1):
            if not doc:
                continue
            
            Logger.info(f"Validating document {i}/{len(docs)}...")
            self.validate_document(doc, args)
        
        # Show results
        print()
        if self.errors:
            print(f"{Colors.RED}✗ {len(self.errors)} error(s) found:{Colors.RESET}")
            for error in self.errors:
                print(f"  • {error}")
        
        if self.warnings:
            print(f"{Colors.YELLOW}⚠ {len(self.warnings)} warning(s):{Colors.RESET}")
            for warning in self.warnings:
                print(f"  • {warning}")
        
        if not self.errors and not self.warnings:
            Logger.success("No issues found!")
        
        # Validate with kubectl
        if args.schema:
            self.kube.run([
                "apply", "-f", args.file,
                "--dry-run=client", "--validate=true"
            ], capture_output=False)
    
    def validate_document(self, doc, args):
        """Validate a single document"""
        kind = doc.get('kind')
        metadata = doc.get('metadata', {})
        spec = doc.get('spec', {})
        
        # Check required fields
        if not kind:
            self.errors.append("Missing 'kind' field")
        
        if not metadata.get('name'):
            self.errors.append("Missing metadata.name")
        
        # Pod/Deployment specific checks
        if kind in ['Pod', 'Deployment']:
            self.validate_pod_spec(spec)
        
        # Security checks
        if args.security:
            self.security_checks(doc)
    
    def validate_pod_spec(self, spec):
        """Validate pod specification"""
        template = spec.get('template', {}).get('spec', {})
        containers = template.get('containers', spec.get('containers', []))
        
        if not containers:
            self.errors.append("No containers defined")
            return
        
        for container in containers:
            # Check resource limits
            resources = container.get('resources', {})
            if not resources.get('limits'):
                self.warnings.append(
                    f"Container '{container.get('name')}' has no resource limits"
                )
            
            # Check image tag
            image = container.get('image', '')
            if ':latest' in image or ':' not in image:
                self.warnings.append(
                    f"Container '{container.get('name')}' uses 'latest' tag"
                )
    
    def security_checks(self, doc):
        """Security best practice checks"""
        spec = doc.get('spec', {})
        template = spec.get('template', {}).get('spec', {})
        
        # Check for privileged containers
        containers = template.get('containers', spec.get('containers', []))
        for container in containers:
            security_context = container.get('securityContext', {})
            if security_context.get('privileged'):
                self.errors.append(
                    f"Container '{container.get('name')}' runs as privileged"
                )
            
            if not security_context.get('runAsNonRoot'):
                self.warnings.append(
                    f"Container '{container.get('name')}' may run as root"
                )
