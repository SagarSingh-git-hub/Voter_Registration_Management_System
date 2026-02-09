from app import create_app
import os

app = create_app()

print("--- URL MAP ---")
for rule in app.url_map.iter_rules():
    if 'document' in str(rule):
        print(f"Rule: {rule} | Endpoint: {rule.endpoint}")

print("\n--- TEST MATCHING ---")
urls_to_test = [
    '/admin/document/documents/test.jpg',
    '/admin/document/photos/test.png',
    '/admin/document/test.pdf'
]

with app.test_request_context():
    from flask import url_for
    adapter = app.url_map.bind('localhost')
    
    for url in urls_to_test:
        try:
            match = adapter.match(url)
            print(f"URL: {url} -> Matched: {match}")
        except Exception as e:
            print(f"URL: {url} -> Error: {e}")

print("\n--- CONFIG CHECK ---")
print(f"UPLOAD_FOLDER: {app.config['UPLOAD_FOLDER']}")
print(f"Exists: {os.path.exists(app.config['UPLOAD_FOLDER'])}")
