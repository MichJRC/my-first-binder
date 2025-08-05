from flask import Flask

app = Flask(__name__)

print(f"Module name: {__name__}")
print(f"Flask app name: {app.name}")
print(f"Flask root path: {app.root_path}")
