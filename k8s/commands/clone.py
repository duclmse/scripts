
"""Clone Kubernetes resources"""
from core.decorators import Command, arg
from core.logger import Logger
import yaml

@Command.register("clone", help="Clone resources", args=[
    arg("resource_type", help="Resource type to clone"),
    arg("source", help="Source resource name"),
    arg("destination", help="Destination resource name"),
    arg("--to-namespace", help="Clone to different namespace"),
    arg("--modifications", help="JSON modifications to apply"),
])
class CloneCommand:
    """Clone pods, deployments, services"""
    
    def __init__(self, kube):
        self.kube = kube
    
    def execute(self, args):
        Logger.info(f"Cloning {args.resource_type}/{args.source} to {args.destination}...")
        
        # Get source resource
        result = self.kube.run([
            "get", args.resource_type, args.source,
            "-n", self.kube.namespace,
            "-o", "yaml"
        ])
        
        # Parse and modify
        resource = yaml.safe_load(result.stdout)
        
        # Remove metadata that shouldn't be cloned
        resource['metadata']['name'] = args.destination
        resource['metadata'].pop('uid', None)
        resource['metadata'].pop('resourceVersion', None)
        resource['metadata'].pop('creationTimestamp', None)
        resource['metadata'].pop('selfLink', None)
        
        # Apply modifications
        if args.modifications:
            import json
            mods = json.loads(args.modifications)
            self.apply_modifications(resource, mods)
        
        # Change namespace if requested
        target_ns = args.to_namespace or self.kube.namespace
        resource['metadata']['namespace'] = target_ns
        
        # Save to temp file and apply
        import tempfile
        from pathlib import Path
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(resource, f)
            temp_file = f.name
        
        try:
            self.kube.run(["apply", "-f", temp_file], capture_output=False)
            Logger.success(f"Cloned to {args.destination} in namespace {target_ns}")
        finally:
            Path(temp_file).unlink()
    
    def apply_modifications(self, resource, mods):
        """Apply JSON modifications to resource"""
        for key, value in mods.items():
            keys = key.split('.')
            current = resource
            for k in keys[:-1]:
                current = current.setdefault(k, {})
            current[keys[-1]] = value
