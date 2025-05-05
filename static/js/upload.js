const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('fileInput');
const preview = document.getElementById('preview');
const comparisonNameInput = document.getElementById('comparison-name');
const showNameInput = document.getElementById('show-name');
const tagsInput = document.getElementById('tags');
let groupedFiles = new Map(); // Maps column prefixes to files
let selectedFiles = new Set();
let columnPrefixes = [];
let columnCount = 2; // Initialize with minimum columns
let rowCount = 1;    // Initialize with one row
let maxColumns = 10; // Maximum allowed columns
let maxRows = 10;    // Maximum allowed rows
let columnNamePrefix = 'column'; // New dynamic column naming
let baseColumns = 0; // Track columns from uploaded files
let addedColumns = 0; // Track manually added columns
let columnIndexMap = new Map(); // Track column indices
let detectedColumns = 2; // Track actual columns from uploaded files
let minColumns = 2; // Define minimum required columns
let columnTracker = new Map(); // Track column assignments
let uploadInProgress = false;
// Variables for drag and drop column reordering
let dragSrcColumn = null;
let draggedColumnIndex = -1;
let isDragging = false;

// Add this new structure to organize files by row and column
let fileMatrix = []; // 2D array to store files by [row][column]

console.log('Upload.js initialized');

dropZone.addEventListener('click', () => fileInput.click());

dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    e.stopPropagation();
    dropZone.classList.add('dragover');
});

dropZone.addEventListener('dragenter', (e) => {
    e.preventDefault();
    dropZone.classList.add('dragover');
});

dropZone.addEventListener('dragleave', () => {
    dropZone.classList.remove('dragover');
});

dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    e.stopPropagation();
    dropZone.classList.remove('dragover');
    const droppedFiles = Array.from(e.dataTransfer.files);
    handleFiles(droppedFiles);
});

fileInput.addEventListener('change', (e) => {
    handleFiles(e.target.files);
});

// Add horizontal scroll handling
preview.addEventListener('wheel', (e) => {
    if (e.deltaY !== 0 && e.shiftKey) {
        e.preventDefault();
        preview.scrollLeft += e.deltaY;
    }
});

function handleFiles(files) {
    if (!files || files.length === 0) return;
    preview.innerHTML = '';
    preview.style.width = '100%';
    const uploadButton = document.getElementById('uploadButton');
    try {
        groupFiles(Array.from(files));
        uploadButton.style.display = 'block';
    } catch (error) {
        showError(error.message);
        uploadButton.style.display = 'none';
    }
}

function groupFiles(files) {
    groupedFiles.clear();
    selectedFiles.clear();
    fileMatrix = []; // Reset the file matrix
    
    // Initialize matrix with empty arrays for each row and column
    for (let r = 0; r < rowCount; r++) {
        fileMatrix[r] = [];
        for (let c = 0; c < columnCount; c++) {
            fileMatrix[r][c] = null;
        }
    }
    
    // Validate file count
    if (files.length > 30) {
        throw new Error('Maximum 30 files allowed');
    }

    // Remove any existing reordering instructions
    const existingInstructions = document.querySelector('.reordering-instructions');
    if (existingInstructions) {
        existingInstructions.remove();
    }

    // Parse filenames and check if they follow the pattern
    const filenameRegex = /^(.+?)(\d+)\.([^.]+)$/i;
    const fileGroups = new Map();
    let patternMatchCount = 0;

    files.forEach(file => {
        const match = file.name.match(filenameRegex);
        if (match) {
            patternMatchCount++;
            const [_, prefix, number, ext] = match;
            const columnPrefix = prefix.toLowerCase();
            const rowNumber = parseInt(number);

            if (!fileGroups.has(columnPrefix)) {
                fileGroups.set(columnPrefix, new Map());
            }
            fileGroups.get(columnPrefix).set(rowNumber, file);
        }
        selectedFiles.add(file);
    });

    // If all files match the pattern, use pattern grouping
    if (patternMatchCount === files.length) {
        // Get unique row numbers
        const rowNumbers = new Set();
        fileGroups.forEach((rowMap) => {
            rowMap.forEach((file, rowNum) => {
                rowNumbers.add(rowNum);
            });
        });
        
        // Update row count based on detected rows
        rowCount = Math.max(1, rowNumbers.size);
        
        // Initialize file matrix with proper size
        fileMatrix = [];
        for (let r = 0; r < rowCount; r++) {
            fileMatrix[r] = [];
            for (let c = 0; c < columnCount; c++) {
                fileMatrix[r][c] = null;
            }
        }
        
        // Validate column counts and consistency
        const columnSizes = Array.from(fileGroups.values()).map(group => group.size);
        columnPrefixes = Array.from(fileGroups.keys());
        detectedColumns = columnPrefixes.length;
        baseColumns = detectedColumns;
        columnCount = Math.max(minColumns, detectedColumns);

        // Place files in the matrix based on pattern
        fileGroups.forEach((rowMap, columnPrefix) => {
            const columnIndex = columnPrefixes.indexOf(columnPrefix);
            rowMap.forEach((file, rowNum) => {
                // Adjust row number to 0-indexed
                const rowIndex = rowNum - 1;
                if (rowIndex >= 0 && rowIndex < rowCount) {
                    // Ensure the row exists
                    if (!fileMatrix[rowIndex]) {
                        fileMatrix[rowIndex] = [];
                    }
                    fileMatrix[rowIndex][columnIndex] = file;
                }
            });
        });
        
        // Store grouped files for backwards compatibility
        fileGroups.forEach((files, prefix) => {
            groupedFiles.set(prefix, Array.from(files.values()));
        });
    } else {
        // For arbitrary filenames, create columns based on file order
        columnCount = Math.min(Math.max(minColumns, files.length), maxColumns);
        baseColumns = 0;
        detectedColumns = columnCount;
        
        // Create column prefixes
        columnPrefixes = [];
        for (let i = 0; i < columnCount; i++) {
            columnPrefixes.push(`column${i+1}`);
            groupedFiles.set(`column${i+1}`, []);
        }
        
        // Initialize row count to 1 for arbitrary filenames
        rowCount = Math.ceil(files.length / columnCount);
        
        // Initialize file matrix with proper size
        fileMatrix = [];
        for (let r = 0; r < rowCount; r++) {
            fileMatrix[r] = [];
            for (let c = 0; c < columnCount; c++) {
                fileMatrix[r][c] = null;
            }
        }
        
        // Distribute files across rows and columns
        files.forEach((file, index) => {
            const rowIndex = Math.floor(index / columnCount);
            const columnIndex = index % columnCount;
            
            // Ensure we don't exceed matrix dimensions
            if (rowIndex < rowCount && columnIndex < columnCount) {
                fileMatrix[rowIndex][columnIndex] = file;
                
                // Also add to groupedFiles for backward compatibility
                const columnPrefix = columnPrefixes[columnIndex];
                if (!groupedFiles.has(columnPrefix)) {
                    groupedFiles.set(columnPrefix, []);
                }
                groupedFiles.get(columnPrefix).push(file);
            }
        });
        
        // Add a note about reordering for arbitrary filenames
        const instructionEl = document.createElement('div');
        instructionEl.className = 'reordering-instructions';
        instructionEl.innerHTML = `
            <div class="alert alert-info mt-2">
                <i class="fas fa-info-circle"></i> 
                Files have been arranged based on upload order. 
                <strong>Drag the column handles <i class="fas fa-grip-lines"></i> to reorder columns</strong> and 
                <strong>use the Add Row button to add new rows</strong> before uploading.
            </div>
        `;
        
        // Insert the instructions above the preview
        preview.parentNode.insertBefore(instructionEl, preview);
    }

    updatePreview();
}

function detectColumnCount(files) {
    const prefixSet = new Set();
    const filenameRegex = /^(.+?)(\d+)\.([^.]+)$/;
    
    files.forEach(file => {
        const match = file.name.match(filenameRegex);
        if (match) {
            prefixSet.add(match[1].toLowerCase());
        }
    });
    
    return Math.max(minColumns, prefixSet.size);
}

function updatePreview() {
    preview.innerHTML = '';
    
    // Create top-level column controls
    const columnControlsBar = document.createElement('div');
    columnControlsBar.className = 'column-controls-bar';
    
    // Add column headers with drag handles
    for (let colIndex = 0; colIndex < columnCount; colIndex++) {
        const columnHeader = document.createElement('div');
        columnHeader.className = 'column-header';
        columnHeader.dataset.columnIndex = colIndex;
        columnHeader.style.width = `calc(100% / ${columnCount})`;
        
        const dragHandle = document.createElement('div');
        dragHandle.className = 'drag-handle';
        dragHandle.innerHTML = '<i class="fas fa-grip-lines"></i>';
        dragHandle.title = 'Drag to reorder this column in all rows';
        dragHandle.draggable = true;
        
        const columnLabel = document.createElement('div');
        columnLabel.className = 'column-label';
        columnLabel.textContent = `Column ${colIndex+1}`;
        
        const removeButton = document.createElement('button');
        removeButton.className = 'btn btn-sm btn-danger';
        removeButton.innerHTML = '<i class="fas fa-times"></i>';
        removeButton.title = 'Remove this column from all rows';
        removeButton.onclick = () => removeColumn(colIndex);
        removeButton.disabled = columnCount <= minColumns;
        
        columnHeader.appendChild(dragHandle);
        columnHeader.appendChild(columnLabel);
        
        // Only add remove button if we have more than minimum columns
        if (columnCount > minColumns) {
            columnHeader.appendChild(removeButton);
        }
        
        columnControlsBar.appendChild(columnHeader);
    }
    
    preview.appendChild(columnControlsBar);
    
    // Create rows
    for (let rowIndex = 0; rowIndex < rowCount; rowIndex++) {
        const rowContainer = document.createElement('div');
        rowContainer.className = 'row-container';
        rowContainer.dataset.rowIndex = rowIndex;
        
        // Add row header with controls
        const rowControls = document.createElement('div');
        rowControls.className = 'row-controls';
        
        const rowLabel = document.createElement('div');
        rowLabel.className = 'row-label';
        rowLabel.textContent = `Row ${rowIndex + 1}`;
        
        const removeRowBtn = document.createElement('button');
        removeRowBtn.className = 'btn btn-sm btn-danger';
        removeRowBtn.innerHTML = '<i class="fas fa-trash"></i> Remove Row';
        removeRowBtn.onclick = () => removeRow(rowIndex);
        removeRowBtn.disabled = rowCount <= 1; // Disable if only one row
        
        rowControls.appendChild(rowLabel);
        rowControls.appendChild(removeRowBtn);
        rowContainer.appendChild(rowControls);
        
        // Create row content container
        const rowColumnsContainer = document.createElement('div');
        rowColumnsContainer.className = 'row-columns';
        
        // Add columns to this row
        for (let colIndex = 0; colIndex < columnCount; colIndex++) {
            const columnDiv = createColumnElement(rowIndex, colIndex);
            rowColumnsContainer.appendChild(columnDiv);
        }
        
        rowContainer.appendChild(rowColumnsContainer);
        preview.appendChild(rowContainer);
    }
    
    // Add drag-and-drop column reordering to the column headers
    enableColumnReordering();
}

// Helper function to create a column element
function createColumnElement(rowIndex, colIndex) {
    const columnPrefix = columnPrefixes[colIndex] || `column${colIndex+1}`;
    const columnDiv = document.createElement('div');
    columnDiv.className = 'comparison-column';
    columnDiv.id = `column-${rowIndex}-${colIndex}`; // Simplified ID format
    columnDiv.dataset.columnIndex = colIndex;
    columnDiv.dataset.rowIndex = rowIndex;
    
    // No controls in the column div anymore - they've moved to the top level
    
    const filesDiv = document.createElement('div');
    filesDiv.className = 'column-files';
    columnDiv.appendChild(filesDiv);
    
    // If we have a file in this position, display it
    if (fileMatrix && fileMatrix[rowIndex] && fileMatrix[rowIndex][colIndex]) {
        displayFilePreview(fileMatrix[rowIndex][colIndex], filesDiv);
    }
    
    return columnDiv;
}

// Helper function to display a file preview
function displayFilePreview(file, container) {
    if (!file) return;
    
    const reader = new FileReader();
    reader.onload = (e) => {
        const fileDiv = document.createElement('div');
        fileDiv.className = 'file-preview';
        fileDiv.innerHTML = `
            <img src="${e.target.result}" style="max-height: 100px;">
            <div class="file-label">${file.name}</div>
        `;
        container.appendChild(fileDiv);
    };
    reader.readAsDataURL(file);
}

// Function to enable column reordering via drag and drop
function enableColumnReordering() {
    const columnHeaders = document.querySelectorAll('.column-header');
    
    columnHeaders.forEach(header => {
        const dragHandle = header.querySelector('.drag-handle');
        if (!dragHandle) return;
        
        // Drag start event
        dragHandle.addEventListener('dragstart', (e) => {
            dragSrcColumn = header;
            draggedColumnIndex = parseInt(header.dataset.columnIndex);
            header.classList.add('dragging');
            e.dataTransfer.effectAllowed = 'move';
            // Required for Firefox
            e.dataTransfer.setData('text/plain', header.dataset.columnIndex);
            preview.classList.add('reordering');
        });
        
        // Drag end event
        dragHandle.addEventListener('dragend', (e) => {
            header.classList.remove('dragging');
            dragSrcColumn = null;
            draggedColumnIndex = -1;
            preview.classList.remove('reordering');
            
            // Remove all drag-over classes
            document.querySelectorAll('.drag-over').forEach(el => {
                el.classList.remove('drag-over');
            });
        });
        
        // Make the entire header a drop target
        header.addEventListener('dragover', (e) => {
            e.preventDefault();
            if (!dragSrcColumn || header === dragSrcColumn) return;
            header.classList.add('drag-over');
        });
        
        header.addEventListener('dragleave', (e) => {
            header.classList.remove('drag-over');
        });
        
        header.addEventListener('drop', (e) => {
            e.preventDefault();
            header.classList.remove('drag-over');
            
            if (!dragSrcColumn || header === dragSrcColumn) return;
            
            const targetIndex = parseInt(header.dataset.columnIndex);
            
            // Perform the column reordering
            reorderColumns(draggedColumnIndex, targetIndex);
        });
    });
}

function reorderColumns(fromIndex, toIndex) {
    if (fromIndex === toIndex) return;
    
    console.log(`Reordering column from ${fromIndex} to ${toIndex}`);
    
    // Save the column prefixes change
    const movedPrefix = columnPrefixes[fromIndex];
    columnPrefixes.splice(fromIndex, 1);
    columnPrefixes.splice(toIndex, 0, movedPrefix);
    
    // Reorder files in the file matrix for ALL rows
    for (let r = 0; r < fileMatrix.length; r++) {
        if (!fileMatrix[r]) continue;
        
        // Save the column of files we're moving
        const filesInMovedColumn = fileMatrix[r][fromIndex];
        
        // Remove the column
        fileMatrix[r].splice(fromIndex, 1);
        
        // Insert at the new position
        fileMatrix[r].splice(toIndex, 0, filesInMovedColumn);
    }
    
    // Also update the legacy groupedFiles for backwards compatibility
    if (groupedFiles.size > 0) {
        const entries = Array.from(groupedFiles.entries());
        const sortedEntries = [];
        
        // Reorder the entries according to the new column order
        for (let i = 0; i < columnPrefixes.length; i++) {
            const prefix = columnPrefixes[i];
            const entry = entries.find(([key]) => key === prefix);
            if (entry) {
                sortedEntries.push(entry);
            }
        }
        
        // Recreate groupedFiles with the new order
        groupedFiles = new Map(sortedEntries);
    }
    
    console.log('New column order:', columnPrefixes);
    
    // Update the UI
    updatePreview();
}

// Function to add a new row
function addRow() {
    if (rowCount >= maxRows) {
        showError(`Maximum ${maxRows} rows allowed`);
        return;
    }
    
    // Add a new row to our data structure
    fileMatrix[rowCount] = [];
    for (let c = 0; c < columnCount; c++) {
        fileMatrix[rowCount][c] = null;
    }
    
    rowCount++;
    
    // Update the UI to show the new row
    updatePreview();
    console.log(`Added row, now have ${rowCount} rows`);
}

// Function to remove a row
function removeRow(rowIndex) {
    if (rowCount <= 1) {
        showError('Cannot remove the last row');
        return;
    }
    
    // Remove the row from our data structure
    fileMatrix.splice(rowIndex, 1);
    rowCount--;
    
    // Update the UI
    updatePreview();
    console.log(`Removed row ${rowIndex + 1}, now have ${rowCount} rows`);
}

function isColumnRemovable(columnPrefix) {
    const isBaseColumn = columnPrefixes.indexOf(columnPrefix) < baseColumns;
    const totalRemaining = columnCount - 1;
    return !isBaseColumn || (isBaseColumn && baseColumns > minColumns);
}

function getColumnTooltip(columnPrefix) {
    const isBaseColumn = columnPrefixes.indexOf(columnPrefix) < baseColumns;
    if (isBaseColumn) {
        if (baseColumns <= minColumns) {
            return 'Cannot remove base columns below minimum';
        }
        return 'Remove base column';
    }
    return 'Remove added column';
}

// Update the column addition function for consistency
function addColumn() {
    if (columnCount >= maxColumns) {
        showError(`Maximum ${maxColumns} columns allowed`);
        return;
    }
    
    // Add a new column prefix
    columnPrefixes.push(`column${columnCount+1}`);
    
    // Add a new column to each row in the file matrix
    for (let r = 0; r < rowCount; r++) {
        if (!fileMatrix[r]) {
            fileMatrix[r] = [];
        }
        fileMatrix[r].push(null);
    }
    
    // Add an empty array for new column in groupedFiles
    if (groupedFiles.size > 0) {
        groupedFiles.set(`column${columnCount+1}`, []);
    }
    
    // Update column count
    columnCount++;
    
    // Update the UI
    updatePreview();
}

// Update the removeColumn function to work with column index
function removeColumn(columnIndex) {
    console.log(`Attempting to remove column at index: ${columnIndex}`);
    
    // Check minimum column requirements
    if (columnCount <= minColumns) {
        showError(`Cannot remove column: Minimum ${minColumns} columns required`);
        return;
    }
    
    // Validate column index
    if (columnIndex < 0 || columnIndex >= columnCount) {
        console.error('Invalid column index:', columnIndex);
        showError('Invalid column');
        return;
    }
    
    // Remove the column from prefixes array
    columnPrefixes.splice(columnIndex, 1);
    
    // Update column count
    columnCount--;
    
    // Remove the column from each row in the file matrix
    for (let r = 0; r < fileMatrix.length; r++) {
        if (fileMatrix[r]) {
            fileMatrix[r].splice(columnIndex, 1);
        }
    }
    
    // Update groupedFiles if it's being used
    if (groupedFiles.size > 0) {
        // Remove the deleted column
        groupedFiles.delete(`column${columnIndex+1}`);
        
        // Rename remaining columns to maintain sequential numbering
        const newGroupedFiles = new Map();
        for (let i = 0; i < columnCount; i++) {
            const oldKey = `column${i >= columnIndex ? i+2 : i+1}`;
            const newKey = `column${i+1}`;
            
            if (groupedFiles.has(oldKey)) {
                newGroupedFiles.set(newKey, groupedFiles.get(oldKey));
            }
        }
        groupedFiles = newGroupedFiles;
    }
    
    // Regenerate column prefixes with correct numbering
    columnPrefixes = [];
    for (let i = 0; i < columnCount; i++) {
        columnPrefixes.push(`column${i+1}`);
    }
    
    console.log(`Column removed. New column count: ${columnCount}`);
    console.log('New column prefixes:', columnPrefixes);
    
    // Update the UI
    updatePreview();
}

function updateColumnControls() {
    document.querySelectorAll('.column-controls button').forEach(button => {
        const columnPrefix = button.closest('.comparison-column').id.split('-')[1];
        button.disabled = !isColumnRemovable(columnPrefix);
        button.title = getColumnTooltip(columnPrefix);
    });
}

function showError(message) {
    const errorDiv = document.createElement('div');
    errorDiv.className = 'error-message';
    errorDiv.textContent = message;
    preview.insertAdjacentElement('beforebegin', errorDiv);
}

function validateMetadata() {
    const comparisonName = comparisonNameInput.value.trim();
    if (!comparisonName) {
        showError('Please enter a comparison name');
        return false;
    }
    if (columnCount < minColumns) {
        showError(`Minimum of ${minColumns} columns required`);
        return false;
    }
    return true;
}

function getMetadata() {
    return {
        name: comparisonNameInput.value.trim(),
        show_name: showNameInput.value.trim(),
        tags: tagsInput.value.trim()
    };
}

function clearMetadata() {
    comparisonNameInput.value = '';
    showNameInput.value = '';
    tagsInput.value = '';
}

document.getElementById('uploadButton').addEventListener('click', async () => {
    const formData = new FormData();
    
    if (uploadInProgress) {
        alert('Upload already in progress');
        return;
    }

    if (selectedFiles.size === 0) {
        alert('Please select or drag some images first');
        return;
    }

    if (!validateMetadata()) {
        return;
    }
    const metadata = getMetadata();

    if (selectedFiles.size > 10) {
        alert('Maximum 10 files allowed');
        return;
    }

    if (columnCount < minColumns) {
        showError('Minimum number of columns required');
        return;
    }

    uploadInProgress = true;
    const uploadButton = document.getElementById('uploadButton');
    uploadButton.disabled = true;
    uploadButton.textContent = 'Uploading...';

    for (const file of selectedFiles) {
        formData.append('files', file);
    }

    // Add column order information to the form data
    formData.append('column_order', JSON.stringify(columnPrefixes));

    formData.append('name', metadata.name);
    formData.append('show_name', metadata.show_name);
    formData.append('tags', metadata.tags);

    try {
        const response = await fetch('/upload/', {
            method: 'POST',
            body: formData
        });
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        console.log('Upload response received:', response);
        const data = await response.json();
        console.log('Upload response data:', data);
        clearMetadata();
        window.location.href = `/compare/${data.comparison_id}`;
    } catch (error) {
        console.error('Upload failed:', error);
        showError('Upload failed: ' + error.message);
    } finally {
        uploadInProgress = false;
        uploadButton.disabled = false;
        uploadButton.textContent = 'Compare Images';
    }
});

// Add the row button in the UI
function addRowButton() {
    const rowButtonContainer = document.createElement('div');
    rowButtonContainer.className = 'row-button-container mb-3';
    
    const addRowBtn = document.createElement('button');
    addRowBtn.id = 'addRowBtn';
    addRowBtn.className = 'btn btn-secondary mb-3 me-2';
    addRowBtn.innerHTML = '<i class="fas fa-plus"></i> Add Row';
    addRowBtn.onclick = addRow;
    
    rowButtonContainer.appendChild(addRowBtn);
    
    // Insert before the preview element
    preview.parentNode.insertBefore(rowButtonContainer, preview);
}

// Call this after the page loads
window.addEventListener('DOMContentLoaded', function() {
    // Initialize the first row in the file matrix
    fileMatrix[0] = [];
    for (let c = 0; c < columnCount; c++) {
        fileMatrix[0][c] = null;
    }
    
    // Add the row button to the UI
    addRowButton();
});
