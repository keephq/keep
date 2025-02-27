import yaml
from yaml import YAMLError

# Define what symbols are exported from this module
__all__ = ['YAMLError', 'safe_load', 'dump', 'add_representer']

class QuotedString(str):
    """A string that remembers if it was quoted in the original YAML."""
    quote_style: str | None = None
    
    def __new__(cls, value, quote_style=None):
        instance = super().__new__(cls, value)
        instance.quote_style = quote_style
        return instance

class QuotePreservingLoader(yaml.CSafeLoader):
    """A YAML Loader that marks strings that were originally quoted."""
    
    def construct_scalar(self, node):
        # Get the scalar value
        value = super().construct_scalar(node)
        
        # If the node had quotes in the original YAML, mark it
        if node.style in ('"', "'"):
            # Use a custom class to remember that this string was quoted
            return QuotedString(value, node.style)
        
        return value

class QuotePreservingDumper(yaml.CDumper):
    """A YAML Dumper that preserves quotes for marked strings."""
    
    def represent_scalar(self, tag, value, style=None):
        # If this is our special QuotedString, use its original quote style
        if isinstance(value, QuotedString) and value.quote_style:
            style = value.quote_style
            
        return super().represent_scalar(tag, value, style)

# Register a proper representer for QuotedString
def represent_quoted_string(dumper, data):
    return dumper.represent_scalar('tag:yaml.org,2002:str', str(data), style=data.quote_style)

QuotePreservingDumper.add_representer(QuotedString, represent_quoted_string)

def safe_load(stream):
    """Load YAML content safely, preserving information about quoted strings."""
    return yaml.load(stream, Loader=QuotePreservingLoader)

def dump(data, stream=None, Dumper=None, **kwds):
    """
    Dump YAML data while preserving quotes in strings that were originally quoted.
    
    Args:
        data: The Python object to dump as YAML
        stream: Optional stream to write to (if None, returns a string)
        Dumper: Optional custom YAML dumper class
        **kwds: Additional keyword arguments for yaml.dump
        
    Returns:
        The YAML string if stream is None, otherwise None
    """
    Dumper = Dumper or QuotePreservingDumper
    # Default to no flow style and preserve key order
    kwds.setdefault('default_flow_style', False)
    kwds.setdefault('sort_keys', False)
    return yaml.dump(data, stream, Dumper=Dumper, **kwds)

def add_representer(data_type, representer, Dumper=None):
    """Add a custom representer for a specific data type."""
    Dumper = Dumper or QuotePreservingDumper
    Dumper.add_representer(data_type, representer)