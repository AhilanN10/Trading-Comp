import markdown
import os

def convert():
    input_file = '/Users/ahilannayani/.gemini/antigravity/brain/e1722e60-7bf5-4969-922b-a2f9396acbc6/walkthrough.md'
    output_file = '/Users/ahilannayani/AntiGravity/alpaca_sim/walkthrough.html'
    
    with open(input_file, 'r') as f:
        text = f.read()
        
    # Convert to HTML
    html_content = markdown.markdown(text, extensions=['tables', 'fenced_code'])
    
    # Add CSS for print-friendly format
    full_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Walkthrough</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                line-height: 1.6;
                max_width: 800px;
                margin: 0 auto;
                padding: 20px;
                color: #333;
            }}
            h1, h2, h3 {{ color: #111; }}
            code {{ background: #f4f4f4; padding: 2px 5px; border-radius: 3px; }}
            pre {{ background: #f4f4f4; padding: 15px; overflow-x: auto; border-radius: 5px; }}
            img {{ max_width: 100%; height: auto; border: 1px solid #ddd; border-radius: 5px; margin: 20px 0; }}
            table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            th {{ background-color: #f2f2f2; }}
            blockquote {{ border-left: 4px solid #007bff; margin: 0; padding-left: 15px; color: #555; }}
            @media print {{
                body {{ max_width: 100%; padding: 0; }}
                a {{ text-decoration: none; color: #000; }}
            }}
        </style>
    </head>
    <body>
        {html_content}
    </body>
    </html>
    """
    
    with open(output_file, 'w') as f:
        f.write(full_html)
        
    print(f"Generated {output_file}")

if __name__ == "__main__":
    convert()
