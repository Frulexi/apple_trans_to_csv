document.addEventListener("DOMContentLoaded", function () {
    const table = document.getElementById("editableTable");
    const saveButton = document.getElementById("saveChanges");

    if (table && saveButton) {
        function getTableData() {
            let tableData = [];
            let rows = table.querySelectorAll("tbody tr");

            rows.forEach(row => {
                let rowData = [];
                row.querySelectorAll("td").forEach(cell => {
                    rowData.push(cell.innerText.trim());
                });
                tableData.push(rowData);
            });

            return tableData;
        }

        // Save button event listener
        saveButton.addEventListener("click", function () {
            if (!confirm("Are you sure you want to save the changes?")) return;

            let tableData = getTableData();
            if (tableData.length === 0) {
                alert("No data to save. Ensure you have edited at least one row.");
                return;
            }

            fetch("/update_table", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ data: tableData })
            })
            .then(response => response.json())
            .then(data => alert(data.message))
            .catch(error => {
                console.error("Error:", error);
                alert("An error occurred while saving. Please try again.");
            });
        });

        // Observe changes in the <tbody> to track added/removed rows
        const observer = new MutationObserver(mutations => {
            if (mutations.some(mutation => mutation.type === "childList")) {
                console.log("Table rows updated.");
            }
        });

        observer.observe(table.querySelector("tbody"), { childList: true });
    }
});