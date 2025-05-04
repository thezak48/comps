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
    
    // Validate file count
    if (files.length > 30) {
        throw new Error('Maximum 30 files allowed');
    }

    // Parse filenames and group files
    const filenameRegex = /^(.+?)(\d+)\.([^.]+)$/i;
    const fileGroups = new Map();

    files.forEach(file => {
        const match = file.name.match(filenameRegex);
        if (!match) {
            throw new Error(`Invalid filename format: ${file.name}. Expected: first0001.ext, second0001.ext, etc.`);
        }

        const [_, prefix, number, ext] = match;
        const columnPrefix = prefix.toLowerCase();
        const rowNumber = parseInt(number);

        if (!fileGroups.has(columnPrefix)) {
            fileGroups.set(columnPrefix, new Map());
        }
        fileGroups.get(columnPrefix).set(rowNumber, file);
        selectedFiles.add(file);
    });

    // Validate column counts and consistency
    const columnSizes = Array.from(fileGroups.values()).map(group => group.size);
    if (columnSizes.length < 2) {
        throw new Error('At least 2 columns (prefixes) required');
    }
    if (new Set(columnSizes).size !== 1) {
        throw new Error('All columns must have the same number of files');
    }

    // Update column tracking
    columnPrefixes = Array.from(fileGroups.keys());
    detectedColumns = columnPrefixes.length;
    baseColumns = detectedColumns;
    columnCount = Math.max(minColumns, detectedColumns);

    // Store grouped files
    fileGroups.forEach((files, prefix) => {
        groupedFiles.set(prefix, Array.from(files.values()));
    });

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
        
        const controlsDiv = document.createElement('div');
        controlsDiv.className = 'column-controls';
        controlsDiv.innerHTML = `
            <button class="btn btn-sm btn-danger" onclick="removeColumn('${columnPrefixes[i]}')" 
                ${isColumnRemovable(columnPrefixes[i]) ? '' : 'disabled'} title="${getColumnTooltip(columnPrefixes[i])}">Remove Column</button>
        `;
        
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
    groupedFiles.set(newColumnName, new Map());
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
