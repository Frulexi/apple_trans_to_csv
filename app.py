from flask import Flask, request, render_template, send_file, redirect, url_for, jsonify
import os
import shutil
import cv2
import pytesseract
import pandas as pd
import re
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename

# Initialize Flask app
app = Flask(__name__)

# Directory for storing uploaded images
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def clear_cache():
    """
    Deletes all files from the uploads directory and the CSV file after processing.
    Ensures a fresh start for each upload session.
    """
    shutil.rmtree(UPLOAD_FOLDER, ignore_errors=True)
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    
    if os.path.exists("output_transactions.csv"):
        os.remove("output_transactions.csv")

def extract_text_from_images(image_paths):
    """
    Extracts and processes text from images using OCR.

    Args:
        image_paths (list): List of image file paths.

    Returns:
        list: Extracted text lines from images.
    """
    extracted_text = []
    
    for file_path in image_paths:
        img = cv2.imread(file_path)
        gray_img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray_img, 150, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        text = pytesseract.image_to_string(thresh, config='--psm 6')
        extracted_text.extend(line.strip() for line in text.split("\n") if line.strip())

    return extracted_text

def process_text_to_csv(extracted_text):
    """
    Converts extracted text into structured transaction data and saves it as a CSV file.

    Args:
        extracted_text (list): List of extracted text lines.

    Returns:
        tuple: Path to the saved CSV file and the DataFrame.
    """
    data = {"Note": [], "Date": [], "Amount": []}
    now = datetime.now()

    for i in range(0, len(extracted_text) - 2, 3):
        merchant = re.sub(r"\$.*", "", extracted_text[i]).strip()
        time_reference = extracted_text[i + 2]
        amount_str = extracted_text[i]
        date = now.strftime("%m/%d/%Y")  # Default date if parsing fails

        # Process different date formats
        if re.match(r"\d{1,2}/\d{1,2}/\d{2}", time_reference):
            date = datetime.strptime(time_reference, "%m/%d/%y").strftime("%m/%d/%Y")
        elif "minutes ago" in time_reference or "hours ago" in time_reference:
            hours_ago = int(time_reference.split()[0]) if "hours ago" in time_reference else 0
            date = (now - timedelta(hours=hours_ago)).strftime("%m/%d/%Y")
        elif "Yesterday" in time_reference:
            date = (now - timedelta(days=1)).strftime("%m/%d/%Y")
        else:
            for wday in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]:
                if wday in time_reference:
                    target_day_index = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"].index(wday)
                    current_day_index = now.weekday()
                    days_difference = (current_day_index - target_day_index) % 7
                    date = (now - timedelta(days=days_difference)).strftime("%m/%d/%Y")
                    break

        # Extract transaction amount
        amount = re.search(r"\$([0-9,.]+)", amount_str)
        data["Note"].append(merchant)
        data["Date"].append(date)
        data["Amount"].append(amount.group(1) if amount else "")

    # Convert data to DataFrame and save as CSV
    df = pd.DataFrame(data)
    csv_path = "output_transactions.csv"
    df.to_csv(csv_path, index=False)
    
    return csv_path, df

def save_uploaded_files(uploaded_files):
    """
    Saves uploaded files to the uploads directory and returns file paths.

    Args:
        uploaded_files (list): List of uploaded file objects.

    Returns:
        list: List of saved file paths.
    """
    file_paths = []
    
    for file in uploaded_files:
        filename = secure_filename(file.filename)
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(file_path)
        file_paths.append(file_path)
    
    return file_paths

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    """
    Handles file uploads, extracts text, processes transactions, and renders the table.

    Returns:
        HTML template (table.html or upload.html)
    """
    if request.method == 'POST':
        uploaded_files = request.files.getlist("file")
        image_paths = save_uploaded_files(uploaded_files)
        extracted_text = extract_text_from_images(image_paths)
        csv_path, df = process_text_to_csv(extracted_text)

        # Convert DataFrame to editable HTML table
        df_html = df.to_html(classes='data', index=False).replace("<td>", '<td contenteditable="true">')

        # Fix structure to avoid nested tables
        df_html = df_html.replace("<table border=\"1\" class=\"dataframe data\">", "").replace("</table>", "")

        return render_template("table.html", tables=[df_html], download_ready=True)

    return render_template("upload.html")

@app.route('/download')
def download_file():
    """
    Serves the generated CSV file for download and clears cached files after download.

    Returns:
        File download response or redirects to upload page.
    """
    csv_path = "output_transactions.csv"
    
    if os.path.exists(csv_path):
        response = send_file(csv_path, as_attachment=True)
        clear_cache()
        return response
    
    return redirect(url_for("upload_file"))

@app.route("/update_table", methods=["POST"])
def update_table():
    """
    Handles table edits submitted via JavaScript and updates the CSV file.

    Returns:
        JSON response indicating success or failure.
    """
    data = request.json.get("data")
    
    if not data:
        return jsonify({"message": "No data received"}), 400

    # Convert edited data into DataFrame and save as CSV
    df = pd.DataFrame(data, columns=["Note", "Date", "Amount"])
    df.to_csv("output_transactions.csv", index=False)

    return jsonify({"message": "Table updated successfully!"})

# Run Flask app
if __name__ == '__main__':
    app.run(debug=True)
