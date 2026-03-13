document.addEventListener("DOMContentLoaded", function() {
    const selectAllCheckbox = document.getElementById('selectAll');
    const itemCheckboxes = document.querySelectorAll('.item-checkbox');
    const bulkApplyBtn = document.querySelector('.bulk-apply-btn');

    // Toggle the Apply button based on if any checkbox is selected
    function toggleBulkButton() {
        if (bulkApplyBtn) {
            const anyChecked = Array.from(itemCheckboxes).some(cb => cb.checked);
            bulkApplyBtn.disabled = !anyChecked;
        }
    }

    // Header Checkbox click
    if (selectAllCheckbox) {
        selectAllCheckbox.addEventListener('change', function() {
            itemCheckboxes.forEach(cb => {
                cb.checked = selectAllCheckbox.checked;
            });
            toggleBulkButton();
        });
    }

    // Individual Row Checkbox clicks
    itemCheckboxes.forEach(cb => {
        cb.addEventListener('change', function() {
            const allChecked = Array.from(itemCheckboxes).every(c => c.checked);
            const someChecked = Array.from(itemCheckboxes).some(c => c.checked);

            if (selectAllCheckbox) {
                selectAllCheckbox.checked = allChecked;
                // Indeterminate visual state if some (but not all) are selected
                selectAllCheckbox.indeterminate = someChecked && !allChecked;
            }
            toggleBulkButton();
        });
    });
});