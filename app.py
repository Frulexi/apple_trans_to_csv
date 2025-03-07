from flask import Flask, request, render_template, send_file, redirect, url_for, jsonify, flash
import os
import shutil
import cv2
import pytesseract
import pandas as pd
import re
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
import logging  # Import logging

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.urandom(24) # needed for flash messages

# Configure logging
logging.basicConfig(filename='app.log', level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')

# Directory for storing uploaded images
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'} # accepted file types

def allowed_file(filename):
    """
    Checks if a file has an allowed extension.
    """
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

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
        try:
            img = cv2.imread(file_path)
            gray_img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            _, thresh = cv2.threshold(gray_img, 150, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            text = pytesseract.image_to_string(thresh, config='--psm 6')
            extracted_text.extend(line.strip() for line in text.split("\n") if line.strip())
        except Exception as e:
            logging.error(f"Error during OCR processing of {file_path}: {e}")
            flash(f"Error processing image {os.path.basename(file_path)}. Please check the image and try again.", 'error')

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
        try:
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
        except Exception as e:
            logging.warning(f"Could not parse date: {time_reference}, defaulting to today. Error: {e}")
            flash(f"Could not parse date: {time_reference}, defaulting to today.", 'warning')

        # Extract transaction amount
        try:
            amount = re.search(r"\$([0-9,.]+)", amount_str)
            data["Amount"].append(amount.group(1) if amount else "")
        except Exception as e:
            logging.warning(f"Could not extract amount: {amount_str}. Error: {e}")
            flash(f"Could not extract amount: {amount_str}. Amount set to empty string.", 'warning')
            data["Amount"].append("")
        
        data["Note"].append(merchant)
        data["Date"].append(date)
        

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
        if file and allowed_file(file.filename):
            try:
                filename = secure_filename(file.filename)
                file_path = os.path.join(UPLOAD_FOLDER, filename)
                file.save(file_path)
                file_paths.append(file_path)
            except Exception as e:
                logging.error(f"Failed to save file {file.filename}: {e}")
                flash(f"Failed to save file {file.filename}. Please try again.", 'error')
        else:
            logging.warning(f"Invalid file type uploaded: {file.filename}")
            flash(f"Invalid file type uploaded: {file.filename}. Please upload only image files (png, jpg, jpeg, gif).", 'warning')

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
        
        if not uploaded_files or all(file.filename == '' for file in uploaded_files): # Check if no files were selected
            flash('No files selected for upload.', 'error')
            return render_template('upload.html')

        image_paths = save_uploaded_files(uploaded_files)

        # if there was an error saving a file.
        if not image_paths:
            return render_template("upload.html")
        
        extracted_text = extract_text_from_images(image_paths)

        # no text was extracted
        if not extracted_text:
            flash("No text extracted from image(s). Please check the image quality and try again.", 'error')
            return render_template("upload.html")

        try:
            csv_path, df = process_text_to_csv(extracted_text)
        except Exception as e:
            logging.error(f"Error processing text to CSV: {e}")
            flash("An error occurred while processing the data. Please try again.", 'error')
            return render_template("upload.html")

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
    else:
        logging.error("Attempted to download non-existent CSV file.")
        flash("CSV file not found. Please process a new file.", 'error')
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
        logging.warning("No data received for table update.")
        return jsonify({"message": "No data received"}), 400

    try:
        # Convert edited data into DataFrame and save as CSV
        df = pd.DataFrame(data, columns=["Note", "Date", "Amount"])
        df.to_csv("output_transactions.csv", index=False)
        return jsonify({"message": "Table updated successfully!"})
    except Exception as e:
        logging.error(f"Error updating table: {e}")
        return jsonify({"message": "Failed to update table"}), 500

# Run Flask app
if __name__ == '__main__':
    app.run(debug=False)
from flask import Flask, request, render_template, send_file, redirect, url_for, jsonify, flash
import os
import shutil
import cv2
import pytesseract
import pandas as pd
import re
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
import logging  # Import logging

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.urandom(24) # needed for flash messages

# Configure logging
logging.basicConfig(filename='app.log', level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')

# Directory for storing uploaded images
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'} # accepted file types

def allowed_file(filename):
    """
    Checks if a file has an allowed extension.
    """
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

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
        try:
            img = cv2.imread(file_path)
            gray_img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            _, thresh = cv2.threshold(gray_img, 150, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            text = pytesseract.image_to_string(thresh, config='--psm 6')
            extracted_text.extend(line.strip() for line in text.split("\n") if line.strip())
        except Exception as e:
            logging.error(f"Error during OCR processing of {file_path}: {e}")
            flash(f"Error processing image {os.path.basename(file_path)}. Please check the image and try again.", 'error')

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
        try:
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
        except Exception as e:
            logging.warning(f"Could not parse date: {time_reference}, defaulting to today. Error: {e}")
            flash(f"Could not parse date: {time_reference}, defaulting to today.", 'warning')

        # Extract transaction amount
        try:
            amount = re.search(r"\$([0-9,.]+)", amount_str)
            data["Amount"].append(amount.group(1) if amount else "")
        except Exception as e:
            logging.warning(f"Could not extract amount: {amount_str}. Error: {e}")
            flash(f"Could not extract amount: {amount_str}. Amount set to empty string.", 'warning')
            data["Amount"].append("")
        
        data["Note"].append(merchant)
        data["Date"].append(date)
        

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
        if file and allowed_file(file.filename):
            try:
                filename = secure_filename(file.filename)
                file_path = os.path.join(UPLOAD_FOLDER, filename)
                file.save(file_path)
                file_paths.append(file_path)
            except Exception as e:
                logging.error(f"Failed to save file {file.filename}: {e}")
                flash(f"Failed to save file {file.filename}. Please try again.", 'error')
        else:
            logging.warning(f"Invalid file type uploaded: {file.filename}")
            flash(f"Invalid file type uploaded: {file.filename}. Please upload only image files (png, jpg, jpeg, gif).", 'warning')

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
        
        if not uploaded_files or all(file.filename == '' for file in uploaded_files): # Check if no files were selected
            flash('No files selected for upload.', 'error')
            return render_template('upload.html')

        image_paths = save_uploaded_files(uploaded_files)

        # if there was an error saving a file.
        if not image_paths:
            return render_template("upload.html")
        
        extracted_text = extract_text_from_images(image_paths)

        # no text was extracted
        if not extracted_text:
            flash("No text extracted from image(s). Please check the image quality and try again.", 'error')
            return render_template("upload.html")

        try:
            csv_path, df = process_text_to_csv(extracted_text)
        except Exception as e:
            logging.error(f"Error processing text to CSV: {e}")
            flash("An error occurred while processing the data. Please try again.", 'error')
            return render_template("upload.html")

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
    else:
        logging.error("Attempted to download non-existent CSV file.")
        flash("CSV file not found. Please process a new file.", 'error')
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
        logging.warning("No data received for table update.")
        return jsonify({"message": "No data received"}), 400

    # Convert edited data into DataFrame and save as CSV
    df = pd.DataFrame(data, columns=["Note", "Date", "Amount"])
    df.to_csv("output_transactions.csv", index=False)

    return jsonify({"message": "Table updated successfully!"})

# Run Flask app
if __name__ == '__main__':
    app.run(debug=False)
