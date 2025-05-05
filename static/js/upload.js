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
let maxColumns = 10; // Maximum allowed columns
let columnNamePrefix = 'column'; // New dynamic column naming
let baseColumns = 0; // Track columns from uploaded files
let addedColumns = 0; // Track manually added columns
let columnIndexMap = new Map(); // Track column indices
let detectedColumns = 2; // Track actual columns from uploaded files
let minColumns = 2; // Define minimum required columns
let columnTracker = new Map(); // Track column assignments
let uploadInProgress = false;
// New variables for drag and drop column reordering
let dragSrcColumn = null;
let draggedColumnIndex = -1;
let isDragging = false;

console.log('Upload.js initialized');

// Add CSS styles for the drag and drop functionality
function addDragDropStyles() {
    const styleElement = document.createElement('style');
    styleElement.textContent = `
        .drag-handle {
            cursor: grab;
            padding: 5px;
            margin-right: 5px;
            color: #aaa;
            background: #333;
            border-radius: 4px;
            display: inline-flex;
            align-items: center;
        }
        
        .drag-handle:hover {
            color: white;
            background: #444;
        }
        
        .comparison-column.dragging {
            opacity: 0.5;
            border: 2px dashed #666;
        }
        
        .comparison-column.drag-over {
            border: 2px dashed #3498db;
        }
        
        #preview.reordering .comparison-column {
            transition: transform 0.2s ease;
        }
        
        .column-controls {
            display: flex;
            align-items: center;
            padding: 5px;
            background: #222;
            border-radius: 4px 4px 0 0;
        }
        
        .column-label {
            margin-left: 5px;
            font-weight: bold;
            color: #ccc;
            flex-grow: 1;
        }
        
        .reordering-instructions {
            background-color: #2d2d2d;
            border-radius: 5px;
            padding: 10px;
            margin: 10px 0;
        }
    `;
    document.head.appendChild(styleElement);
}

// Call this function during initialization
addDragDropStyles();

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
        // Validate column counts and consistency
        const columnSizes = Array.from(fileGroups.values()).map(group => group.size);
        if (columnSizes.length < 2) {
            // We need at least 2 columns for comparison
            columnPrefixes = Array.from(fileGroups.keys());
            detectedColumns = columnPrefixes.length;
            baseColumns = detectedColumns;
            columnCount = Math.max(minColumns, detectedColumns);

            // Store grouped files
            fileGroups.forEach((files, prefix) => {
                groupedFiles.set(prefix, Array.from(files.values()));
            });
        } else if (new Set(columnSizes).size !== 1) {
            // Show warning about inconsistent rows, but still process
            console.warn('Columns have different numbers of files - results may be unexpected');
            columnPrefixes = Array.from(fileGroups.keys());
            detectedColumns = columnPrefixes.length;
            baseColumns = detectedColumns;
            columnCount = Math.max(minColumns, detectedColumns);

            // Store grouped files
            fileGroups.forEach((files, prefix) => {
                groupedFiles.set(prefix, Array.from(files.values()));
            });
        } else {
            // Standard pattern matching worked perfectly
            columnPrefixes = Array.from(fileGroups.keys());
            detectedColumns = columnPrefixes.length;
            baseColumns = detectedColumns;
            columnCount = Math.max(minColumns, detectedColumns);

            // Store grouped files
            fileGroups.forEach((files, prefix) => {
                groupedFiles.set(prefix, Array.from(files.values()));
            });
        }
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
        
        // Distribute files across columns
        files.forEach((file, index) => {
            const columnIndex = index % columnCount;
            const columnPrefix = columnPrefixes[columnIndex];
            groupedFiles.get(columnPrefix).push(file);
        });
        
        // Add a note about reordering for arbitrary filenames
        const instructionEl = document.createElement('div');
        instructionEl.className = 'reordering-instructions';
        instructionEl.innerHTML = `
            <div class="alert alert-info mt-2">
                <i class="fas fa-info-circle"></i> 
                Files have been arranged in columns based on upload order. 
                <strong>Drag the column handles <i class="fas fa-grip-lines"></i> to reorder columns</strong> before uploading.
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
    
    // Use full container width
    const containerWidth = window.innerWidth - 40; // Account for margins
    // Update CSS variable for column width
    preview.style.setProperty('--column-width', `${containerWidth / columnCount}px`);

    // Set CSS variable for column count
    preview.style.setProperty('--column-count', columnCount);
    
    // Preserve existing column structure
    for (let i = 0; i < columnCount; i++) {
        // Skip if column prefix doesn't exist
        if (!columnPrefixes[i]) continue;
        const columnDiv = document.createElement('div');
        columnDiv.className = 'comparison-column';
        columnDiv.id = `column-${columnPrefixes[i]}`;
        columnDiv.dataset.columnIndex = i;
        
        const controlsDiv = document.createElement('div');
        controlsDiv.className = 'column-controls';
        
        // Add drag handle
        const dragHandle = document.createElement('div');
        dragHandle.className = 'drag-handle';
        dragHandle.innerHTML = '<i class="fas fa-grip-lines"></i>';
        dragHandle.title = 'Drag to reorder column';
        dragHandle.draggable = true;
        
        // Add column label
        const columnLabel = document.createElement('div');
        columnLabel.className = 'column-label';
        columnLabel.textContent = `Column ${i+1}`;
        
        // Add remove button
        const removeButton = document.createElement('button');
        removeButton.className = 'btn btn-sm btn-danger';
        removeButton.onclick = () => removeColumn(columnPrefixes[i]);
        removeButton.disabled = !isColumnRemovable(columnPrefixes[i]);
        removeButton.title = getColumnTooltip(columnPrefixes[i]);
        removeButton.textContent = 'Remove Column';
        
        controlsDiv.appendChild(dragHandle);
        controlsDiv.appendChild(columnLabel);
        controlsDiv.appendChild(removeButton);
        
        columnDiv.appendChild(controlsDiv);
        
        const filesDiv = document.createElement('div');
        filesDiv.className = 'column-files';
        columnDiv.appendChild(filesDiv);
        
        preview.appendChild(columnDiv);
    }
    
    // Update files in columns
    groupedFiles.forEach((files, prefix) => {
        const columnDiv = document.getElementById(`column-${prefix}`);
        if (columnDiv) {
            const filesDiv = columnDiv.querySelector('.column-files');
            files.forEach(file => {
                const reader = new FileReader();
                reader.onload = (e) => {
                    const fileDiv = document.createElement('div');
                    fileDiv.className = 'file-preview';
                    fileDiv.innerHTML = `
                        <img src="${e.target.result}" style="max-height: 100px;">
                        <div class="file-label">${file.name}</div>
                    `;
                    filesDiv.appendChild(fileDiv);
                };
                reader.readAsDataURL(file);
            });
        }
    });
    
    // Add drag-and-drop column reordering
    enableColumnReordering();
}

// Function to enable column reordering via drag and drop
function enableColumnReordering() {
    const columns = document.querySelectorAll('.comparison-column');
    
    columns.forEach(column => {
        const dragHandle = column.querySelector('.drag-handle');
        if (!dragHandle) return;
        
        // Drag start event
        dragHandle.addEventListener('dragstart', (e) => {
            dragSrcColumn = column;
            draggedColumnIndex = parseInt(column.dataset.columnIndex);
            column.classList.add('dragging');
            e.dataTransfer.effectAllowed = 'move';
            // Required for Firefox
            e.dataTransfer.setData('text/plain', column.id);
            preview.classList.add('reordering');
        });
        
        // Drag end event
        dragHandle.addEventListener('dragend', (e) => {
            column.classList.remove('dragging');
            dragSrcColumn = null;
            draggedColumnIndex = -1;
            preview.classList.remove('reordering');
            
            // Remove all drag-over classes
            document.querySelectorAll('.drag-over').forEach(el => {
                el.classList.remove('drag-over');
            });
        });
        
        // Make the entire column a drop target
        column.addEventListener('dragover', (e) => {
            e.preventDefault();
            if (!dragSrcColumn || column === dragSrcColumn) return;
            column.classList.add('drag-over');
        });
        
        column.addEventListener('dragleave', (e) => {
            column.classList.remove('drag-over');
        });
        
        column.addEventListener('drop', (e) => {
            e.preventDefault();
            column.classList.remove('drag-over');
            
            if (!dragSrcColumn || column === dragSrcColumn) return;
            
            const targetIndex = parseInt(column.dataset.columnIndex);
            
            // Perform the column reordering
            reorderColumns(draggedColumnIndex, targetIndex);
        });
    });
}

// Function to reorder columns
function reorderColumns(fromIndex, toIndex) {
    if (fromIndex === toIndex) return;
    
    // Get column prefix that was moved
    const movedPrefix = columnPrefixes[fromIndex];
    
    // Remove from original position and insert at new position
    columnPrefixes.splice(fromIndex, 1);
    columnPrefixes.splice(toIndex, 0, movedPrefix);
    
    // Log the reordering for debugging
    console.log(`Reordered column from position ${fromIndex} to ${toIndex}`);
    console.log('New column order:', columnPrefixes);
    
    // Update the UI to reflect the new order
    updatePreview();
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

function addColumn() {
    if (columnCount >= maxColumns) {
        showError(`Maximum ${maxColumns} columns allowed`);
        return;
    }
    
    // Update CSS variable for column count
    preview.style.setProperty('--column-count', columnCount + 1);
    
    // Add resize observer to handle column width updates
    const resizeObserver = new ResizeObserver(entries => {
        preview.style.setProperty('--column-count', columnCount);
    });
    resizeObserver.observe(preview);
    
    columnCount++;
    addedColumns++;
    const newColumnName = `${columnNamePrefix}${columnCount}`;
    columnPrefixes.push(newColumnName);
    groupedFiles.set(newColumnName, []);
    updatePreview();
    updateColumnControls();
}

function removeColumn(columnIndex) {
    try {
        // Validate minimum columns
        if (columnCount <= minColumns) {
            showError('Cannot remove column: Minimum 2 columns required');
            return;
        }

        const index = columnPrefixes.indexOf(columnIndex);
        if (index === -1 || !isColumnRemovable(columnIndex)) {
            console.error('Column not found:', columnIndex);
            showError('Invalid column');
            return;
        }
        
        // Update column counts
        const isBaseColumn = index < baseColumns;
        isBaseColumn ? baseColumns-- : addedColumns--;

        // Remove the column from data structures
        groupedFiles.delete(columnIndex);

        // Update column tracking
        columnCount--;

        // Remove from column prefixes array
        columnPrefixes.splice(index, 1);

        // Reindex remaining columns
        let newPrefixes = [];
        columnPrefixes.forEach((prefix, i) => {
            const newPrefix = `${columnNamePrefix}${i + 1}`;
            if (prefix !== newPrefix) {
                const files = groupedFiles.get(prefix);
                if (files) {
                    groupedFiles.set(newPrefix, files);
                    groupedFiles.delete(prefix);
                }
            }
            newPrefixes.push(newPrefix);
        });
        columnPrefixes = newPrefixes;

        document.getElementById('uploadButton').style.display = selectedFiles.size > 0 ? 'block' : 'none';
        updateColumnControls();
        updatePreview();
    } catch (error) {
        console.error('Error removing column:', error);
        showError('Failed to remove column');
    }
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
