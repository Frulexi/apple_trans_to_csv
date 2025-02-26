document.addEventListener('DOMContentLoaded', function () {
    let fileInput = document.getElementById('fileInput');
    let previewContainer = document.getElementById('preview');
    let fileNameElement = document.getElementById('fileName');
    let convertBtn = document.getElementById('convertBtn');

    // Ensure button is disabled on page load
    convertBtn.disabled = true;

    fileInput.addEventListener('change', function(event) {
        let files = event.target.files;

        // Clear previous previews
        previewContainer.innerHTML = "";
        fileNameElement.textContent = "";
        convertBtn.disabled = true; // Disable button until a valid file is selected

        if (files.length === 0) {
            fileNameElement.textContent = "No file selected";
            return;
        }

        // Filter valid image files
        let validFiles = Array.from(files).filter(file => file.type.startsWith('image/'));

        if (validFiles.length === 0) {
            fileNameElement.textContent = "Invalid file type. Please select images only.";
            return;
        }

        // Display file names
        fileNameElement.textContent = validFiles.map(file => file.name).join(', ');

        // Enable button if at least one valid file is selected
        convertBtn.disabled = false;

        // Show image previews
        validFiles.forEach(file => {
            let reader = new FileReader();
            reader.onload = function(e) {
                let img = document.createElement('img');
                img.src = e.target.result;
                img.style.maxWidth = '100px';
                img.style.margin = '5px';
                img.style.borderRadius = '5px';
                img.style.boxShadow = '0px 0px 5px rgba(0, 0, 0, 0.2)';
                previewContainer.appendChild(img);
            };
            reader.readAsDataURL(file);
        });
    });
});
