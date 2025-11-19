# In app.py, replace the line 'app.run(debug=True)'
# with the following:

from waitress import serve

if __name__ == "__main__":
    # ... (rest of your file structure setup code) ...

    # Use Waitress for Windows production-like serving
    print("Starting Waitress server on http://127.0.0.1:8080")
    serve(app, host='0.0.0.0', port=8080)