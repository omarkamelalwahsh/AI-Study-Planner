import os
import sys
from jinja2 import Environment, FileSystemLoader, TemplateSyntaxError

def check_templates():
    template_dir = os.path.join(os.path.dirname(__file__), '..', 'app', 'templates')
    env = Environment(loader=FileSystemLoader(template_dir))
    
    success = True
    for template_name in os.listdir(template_dir):
        if template_name.endswith('.html'):
            try:
                env.get_template(template_name)
                print(f"PASS: {template_name}")
            except TemplateSyntaxError as e:
                print(f"FAIL: {template_name} at line {e.lineno}: {e.message}")
                success = False
            except Exception as e:
                print(f"ERROR: {template_name}: {e}")
                success = False
                
    return success

if __name__ == "__main__":
    if check_templates():
        print("\n✔ ALL TEMPLATES COMPILE OK")
        sys.exit(0)
    else:
        print("\n✖ SOME TEMPLATES HAVE ERRORS")
        sys.exit(1)
