const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('fileInput');
const preview = document.getElementById('preview');
const comparisonNameInput = document.getElementById('comparison-name');
const showNameInput = document.getElementById('show-name');
const tagsInput = document.getElementById('tags');
const groupedFiles = new Map();
let selectedFiles = new Set();
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

function handleFiles(files) {
    if (!files || files.length === 0) return;
    preview.innerHTML = '';
    document.getElementById('preview').innerHTML = '<div class="grid-preview"></div>';
    const uploadButton = document.getElementById('uploadButton');
    groupFiles(Array.from(files));
}

function groupFiles(files) {
    groupedFiles.clear();
    const fileGroups = new Map();
    selectedFiles.clear();

    // Create a structured map to maintain column and row relationships
    const fileMatrix = new Map();
    ['first', 'second', 'third'].forEach(prefix => {
        fileMatrix.set(prefix, new Map());
    });

    // First pass: organize files into matrix by column and row
    for (const file of files) {
        const match = file.name.match(/^(first|second|third)(\d{4})\.([^.]+)$/i);
        if (!match) {
            showError(`Invalid filename format: ${file.name}`);
            console.error(`Invalid filename format: ${file.name}`);
            continue;
        }
        
        const [, prefix, number] = match;
        const columnKey = prefix.toLowerCase();
        const rowNum = parseInt(number);
        
        fileMatrix.get(columnKey).set(rowNum, file);
    }

    // Validate groups and create preview
    for (const [groupKey, group] of fileMatrix) {
        createGroupPreview(groupKey, group);
        selectedFiles = new Set([...selectedFiles, ...group.values()]);
    }

    document.getElementById('uploadButton').style.display = fileMatrix.size > 0 ? 'block' : 'none';
}

function createGroupPreview(groupKey, group) {
    const groupDiv = document.createElement('div');
    groupDiv.className = 'comparison-column';
    const columnNames = {
        'first': 'Column 1',
        'second': 'Column 2',
        'third': 'Column 3'
    };
    groupDiv.innerHTML = `<h3>${columnNames[groupKey]}</h3>`;

    const filesDiv = document.createElement('div');
    filesDiv.className = 'column-files';

    // Get all row numbers and sort them
    const rowNumbers = Array.from(group.keys()).sort((a, b) => a - b);
    
    // Create previews in order of sorted row numbers
    for (const rowNum of rowNumbers) {
        const file = group.get(rowNum);
        if (!file) continue;
        const reader = new FileReader();
        reader.onload = (e) => {
            const fileDiv = document.createElement('div');
            fileDiv.className = 'file-preview';
            
            const img = document.createElement('img');
            img.src = e.target.result;
            img.style.maxHeight = '100px';
            
            const label = document.createElement('div');
            label.className = 'file-label';
            label.textContent = rowNum.toString();
            
            fileDiv.appendChild(img);
            fileDiv.appendChild(label);
            filesDiv.appendChild(fileDiv);
        };
        reader.readAsDataURL(file);
    }

    groupDiv.appendChild(filesDiv);
    preview.appendChild(groupDiv);
}

function showError(message) {
    const errorDiv = document.createElement('div');
    errorDiv.className = 'error-message';
    errorDiv.textContent = message;
    preview.appendChild(errorDiv);
}

function validateMetadata() {
    const comparisonName = comparisonNameInput.value.trim();
    if (!comparisonName) {
        showError('Comparison name is required');
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
