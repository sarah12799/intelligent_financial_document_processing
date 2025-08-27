// Données globales
let images = [];
let tokensPerPage = []; // Liste des tokens par page avec bboxes
let tableData = [];
let selectedIds = new Set(); // Utilisé pour stocker les IDs présents dans le tableau
let pageDimensions = [];
let highlightedId = null;
let selectedCell = null; // {rowIdx: number, col: string} pour la cellule sélectionnée
let originalFilename = ''; // Pour stocker le nom du fichier original
let documentId = ''; // Stocker l'ID du document généré par l'API
let zoomLevel = 1; // Niveau de zoom initial
const zoomStep = 0.2; // Pas de zoom
const minZoom = 0.5; // Zoom minimum
const maxZoom = 3; // Zoom maximum
let isColored = false; // Nouvel état pour alterner les couleurs

// Mapper les colonnes aux clés de données
const colToDataKey = {
    0: 'compte',
    1: 'solde_an',
    2: 'solde',
    3: 'débit',
    4: 'crédit'
};

// Gérer le drag and drop et l'upload
function handleDragAndDrop(event) {
    event.preventDefault();
    const fileInput = document.getElementById('pdf-upload');
    if (event.type === 'dragover') {
        document.getElementById('drop-zone').classList.add('dragover');
    } else if (event.type === 'dragleave' || event.type === 'drop') {
        document.getElementById('drop-zone').classList.remove('dragover');
    }
    if (event.type === 'drop') {
        const files = event.dataTransfer.files;
        if (files.length > 0 && files[0].type === 'application/pdf') {
            fileInput.files = files;
            originalFilename = files[0].name.split('.')[0]; // Stocker le nom sans extension
            updateFileName(files[0].name);
            document.getElementById('extract-btn').disabled = false;
        }
    }
}

function updateFileName(filename) {
    const fileNameDiv = document.getElementById('file-name');
    fileNameDiv.textContent = `Fichier sélectionné : ${filename}`;
    originalFilename = filename.split('.')[0]; // Mettre à jour le nom sans extension
}

function handleUpload() {
    const fileInput = document.getElementById('pdf-upload');
    if (fileInput.files.length > 0) {
        originalFilename = fileInput.files[0].name.split('.')[0]; // Stocker le nom sans extension
        updateFileName(fileInput.files[0].name);
        document.getElementById('extract-btn').disabled = false;
    } else {
        document.getElementById('extract-btn').disabled = true;
    }
}

// Gérer l'extraction avec progression
async function extractData() {
    const fileInput = document.getElementById('pdf-upload');
    const file = fileInput.files[0];
    if (!file) {
        alert('Veuillez sélectionner un fichier PDF.');
        return;
    }

    const formData = new FormData();
    formData.append('file', file);

    const progressPopup = document.getElementById('progress-popup');
    const progressMessages = document.getElementById('progress-messages');
    const progressBar = document.getElementById('progress-bar');
    progressPopup.classList.remove('hidden');

    const steps = [
        { message: 'Requête envoyée au modèle', progress: 20 },
        { message: 'Extraction faite', progress: 40 },
        { message: 'Conversion en images faite', progress: 60 },
        { message: 'Classification des tokens', progress: 80 },
        { message: 'Reconstruction du tableau', progress: 100 }
    ];

    try {
        let stepIndex = 0;
        const updateProgress = () => {
            if (stepIndex < steps.length) {
                progressMessages.textContent = steps[stepIndex].message;
                progressBar.value = steps[stepIndex].progress;
                stepIndex++;
            }
        };

        updateProgress();
        console.log('Début de la requête fetch vers http://localhost:5001/extract');

        const response = await fetch('http://localhost:5001/extract', {
            method: 'POST',
            body: formData
        });
        console.log('Réponse reçue, statut :', response.status);

        if (!response.ok) {
            const errorText = await response.text();
            console.error('Erreur HTTP :', response.status, errorText);
            alert(`Erreur lors de l'extraction : Statut ${response.status} - ${errorText}`);
            progressPopup.classList.add('hidden');
            return;
        }

        updateProgress();
        const data = await response.json();
        console.log('Données JSON reçues de l\'API :', data);
        updateProgress();

        // Récupérer l'ID du document (ajuster selon la structure réelle de la réponse)
        documentId = data.documentId || (data.length > 0 && data[0].documentId) || '';
        if (!documentId) {
            console.warn('Aucun documentId trouvé dans la réponse API');
        } else {
            console.log(`ID du document généré : ${documentId}`);
        }

        tableData = data.data || (Array.isArray(data) ? data : []);
        images = (data.images || []).map(img => img.replace(/\\/g, '/'));
        pageDimensions = Array(images.length).fill({ width: 595, height: 842 });
        updateProgress();

        const pdfFilename = file.name.split('.')[0];
        const tokensJsonPath = `data/${pdfFilename}.json`;
        const tokensResponse = await fetch(tokensJsonPath);
        const tokensData = await tokensResponse.json();
        tokensPerPage = groupTokensByPage(tokensData);
        console.log('tokensPerPage assigné :', tokensPerPage);
        updateProgress();

        updateSelectedIds();

        const pageSelect = document.getElementById('page-select');
        pageSelect.innerHTML = '';
        images.forEach((_, idx) => {
            const option = document.createElement('option');
            option.value = idx;
            option.textContent = `Page ${idx + 1}`;
            pageSelect.appendChild(option);
        });
        renderTable();
        drawImage(0);

        progressPopup.classList.add('hidden');
    } catch (error) {
        console.error('Erreur détaillée dans extractData :', error);
        alert('Une erreur est survenue lors de l\'appel à l\'API.');
        progressPopup.classList.add('hidden');
    }
}

// Mettre à jour l'ensemble des IDs présents dans tableData
function updateSelectedIds() {
    selectedIds.clear();
    if (!Array.isArray(tableData)) {
        console.error('tableData n\'est pas un tableau :', tableData);
        return;
    }
    tableData.forEach((row, rowIdx) => {
        if (typeof row !== 'object' || row === null) {
            console.warn(`Ligne ${rowIdx} invalide :`, row);
            return;
        }
        ['compte', 'solde_an', 'solde', 'débit', 'crédit'].forEach(col => {
            const field = row[col];
            if (Array.isArray(field) && field.length >= 2 && field[1] != null) {
                const tokenId = String(field[1]);
                selectedIds.add(tokenId);
            }
        });
    });
    console.log('selectedIds mis à jour depuis la réponse LLM :', Array.from(selectedIds));
}

// Grouper les tokens par page
function groupTokensByPage(tokens) {
    const pages = {};
    for (const tok of tokens) {
        const pageNum = tok.page || 0;
        pages[pageNum] = pages[pageNum] || [];
        pages[pageNum].push({
            ...tok,
            id: String(tok.id)
        });
    }
    return Object.keys(pages).sort((a, b) => a - b).map(k => pages[k]);
}

// Vérifier la formule solde = solde_an + débit - crédit avec alternance
function checkBalanceFormula() {
    if (!isColored) {
        // Premier clic : Appliquer les couleurs
        tableData.forEach((row, rowIdx) => {
            const soldeAn = row['solde_an'] && row['solde_an'][0] === 'N/A' ? 0 : parseFloat(row['solde_an'] && row['solde_an'][0]) || 0;
            const solde = parseFloat(row['solde'] && row['solde'][0]) || 0;
            const debit = parseFloat(row['débit'] && row['débit'][0]) || 0;
            const credit = parseFloat(row['crédit'] && row['crédit'][0]) || 0;

            const calculatedSolde = soldeAn + debit - credit;
            const tr = document.querySelector(`#data-table tbody tr:nth-child(${rowIdx + 1})`);
            if (tr && Math.abs(calculatedSolde - solde) < 0.01) { // Tolérance pour arrondis
                tr.classList.remove('invalid-row');
                tr.classList.add('valid-row');
            } else if (tr) {
                tr.classList.remove('valid-row');
                tr.classList.add('invalid-row');
            }
        });
        isColored = true;
    } else {
        // Deuxième clic : Réinitialiser les couleurs
        const tbody = document.querySelector('#data-table tbody');
        if (tbody) {
            const rows = tbody.getElementsByTagName('tr');
            for (let row of rows) {
                row.classList.remove('valid-row', 'invalid-row');
            }
        }
        isColored = false;
    }
    console.log(`Vérification de la formule effectuée, état : ${isColored ? 'coloré' : 'réinitialisé'}`);
}

// Rendre le tableau éditable et cliquable
function renderTable() {
    const tbody = document.querySelector('#data-table tbody');
    if (!tbody) {
        console.error('Élément #data-table tbody manquant');
        return;
    }
    tbody.innerHTML = '';
    if (!Array.isArray(tableData)) {
        console.error('tableData n\'est pas un tableau :', tableData);
        return;
    }

    tableData.forEach((row, rowIdx) => {
        if (typeof row !== 'object' || row === null) {
            console.warn(`Ligne ${rowIdx} n\'est pas un objet :`, row);
            return;
        }
        const tr = document.createElement('tr');
        if (isColored) {
            const soldeAn = row['solde_an'] && row['solde_an'][0] === 'N/A' ? 0 : parseFloat(row['solde_an'] && row['solde_an'][0]) || 0;
            const solde = parseFloat(row['solde'] && row['solde'][0]) || 0;
            const debit = parseFloat(row['débit'] && row['débit'][0]) || 0;
            const credit = parseFloat(row['crédit'] && row['crédit'][0]) || 0;
            const calculatedSolde = soldeAn + debit - credit;
            if (Math.abs(calculatedSolde - solde) < 0.01) {
                tr.classList.add('valid-row');
            } else {
                tr.classList.add('invalid-row');
            }
        }
        ['compte', 'solde_an', 'solde', 'débit', 'crédit'].forEach((col, colIdx) => {
            const td = document.createElement('td');
            let value = 'N/A'; // Valeur par défaut
            let tokenId = null;

            if (row[col]) {
                if (Array.isArray(row[col]) && row[col].length >= 2) {
                    value = row[col][0] || (col === 'solde_an' ? 'N/A' : '0');
                    tokenId = String(row[col][1]);
                } else {
                    value = col === 'solde_an' ? 'N/A' : '0';
                }
            } else {
                value = col === 'solde_an' ? 'N/A' : '0';
            }

            const input = document.createElement('input');
            input.type = 'text';
            input.value = value;
            input.dataset.row = rowIdx;
            input.dataset.col = col;
            input.dataset.tokenId = tokenId;

            if (selectedCell && selectedCell.rowIdx == rowIdx && selectedCell.col == col) {
                input.classList.add('selected-cell');
            }

            // Événement change
            input.addEventListener('change', (e) => {
                const newValue = e.target.value;
                tableData[rowIdx][col] = [newValue || (col === 'solde_an' ? 'N/A' : '0'), tokenId];
                console.log(`Valeur mise à jour pour row=${rowIdx}, col=${col} : ${newValue}`);
                renderTable(); // Re-rendre pour refléter la mise à jour
            });

            // Événement clic pour sélectionner la cellule
            input.addEventListener('click', () => {
                if (selectedCell) {
                    const oldInput = document.querySelector(`input[data-row="${selectedCell.rowIdx}"][data-col="${selectedCell.col}"]`);
                    if (oldInput) oldInput.classList.remove('selected-cell');
                }
                selectedCell = { rowIdx, col };
                input.classList.add('selected-cell');
                highlightedId = tokenId;
                console.log(`Cellule sélectionnée pour correction : rowIdx=${rowIdx}, col=${col}`);
                drawImage(document.getElementById('page-select').value);
            });

            // Événement double-clic pour vider la cellule
            input.addEventListener('dblclick', () => {
                console.log('Double-clic détecté sur la cellule');
                if (tableData[rowIdx] && tableData[rowIdx].hasOwnProperty(col)) {
                    const defaultValue = col === 'solde_an' ? 'N/A' : '0';
                    const oldTokenId = tokenId;
                    tableData[rowIdx][col] = [defaultValue, null]; // Vider la valeur et l'ID
                    console.log(`Cellule vidée : row=${rowIdx}, col=${col}, nouvelle valeur=${defaultValue}, ancien ID=${oldTokenId}`);
                    if (oldTokenId) {
                        selectedIds.delete(oldTokenId);
                        console.log(`ID ${oldTokenId} supprimé de selectedIds`);
                    }
                    renderTable(); // Re-rendre le tableau
                    drawImage(document.getElementById('page-select').value); // Rafraîchir le canvas
                    selectedCell = null; // Désélectionner après vidage
                } else {
                    console.error(`Erreur : tableData[${rowIdx}][${col}] non accessible`);
                }
            });
            console.log(`Écouteur dblclick attaché à input pour row=${rowIdx}, col=${col}`);

            td.appendChild(input);
            tr.appendChild(td);
        });
        tbody.appendChild(tr);
    });
}

// Dessiner l'image avec les bboxes
function drawImage(pageIdx) {
    console.log(`Début de drawImage pour page ${pageIdx}, images[${pageIdx}] :`, images[pageIdx]);
    const canvas = document.getElementById('image-canvas');
    const ctx = canvas.getContext('2d');
    const img = new Image();
    img.src = images[pageIdx] || '';
    img.onload = () => {
        console.log(`Image chargée, dimensions : ${img.width}x${img.height}`);
        // Ajuster les dimensions du canvas au conteneur avec support HiDPI pour meilleure qualité
        const container = canvas.parentElement;
        const dpr = window.devicePixelRatio || 1;
        const logicalWidth = container.clientWidth;
        const logicalHeight = container.clientHeight;
        canvas.width = logicalWidth * dpr * zoomLevel;
        canvas.height = logicalHeight * dpr * zoomLevel;
        canvas.style.width = `${logicalWidth}px`;
        canvas.style.height = `${logicalHeight}px`;
        ctx.scale(dpr * zoomLevel, dpr * zoomLevel);
        ctx.imageSmoothingEnabled = true;
        ctx.imageSmoothingQuality = 'high';

        ctx.drawImage(img, 0, 0, logicalWidth, logicalHeight);

        const tokens = tokensPerPage[pageIdx] || [];
        const { width: pdfWidth, height: pdfHeight } = pageDimensions[pageIdx] || { width: 595, height: 842 };

        // Déterminer les tokens à dessiner : tous si une cellule est sélectionnée, sinon seulement les sélectionnés
        const drawTokens = selectedCell ? tokens : tokens.filter(tok => selectedIds.has(String(tok.id)));

        console.log('Tokens totaux sur la page :', tokens.length);
        console.log('Tokens à dessiner :', drawTokens.length);

        for (const tok of drawTokens) {
            const { x0, y0, x1, y1, id } = tok;
            const leftPx = (x0 / pdfWidth) * logicalWidth;
            const rightPx = (x1 / pdfWidth) * logicalWidth;
            const topPx = (y0 / pdfHeight) * logicalHeight;
            const bottomPx = (y1 / pdfHeight) * logicalHeight;
            const widthPx = rightPx - leftPx;
            const heightPx = bottomPx - topPx;

            const isAssigned = selectedIds.has(String(id));
            const isHighlighted = String(id) === highlightedId;
            let fillColor;
            if (isHighlighted) {
                fillColor = 'rgba(255, 215, 0, 0.5)'; // Jaune pastel plus vif
            } else if (isAssigned) {
                fillColor = 'rgba(135, 219, 247, 0.4)'; // Bleu pastel pour assigné
            } else {
                fillColor = 'rgba(211, 211, 211, 0.3)'; // Gris clair pour non assigné
            }
            ctx.fillStyle = fillColor;

            const radius = 10; // Rayon pour arrondir les coins (en pixels logiques)

            ctx.beginPath();
            ctx.moveTo(leftPx + radius, topPx);
            ctx.lineTo(rightPx - radius, topPx);
            ctx.quadraticCurveTo(rightPx, topPx, rightPx, topPx + radius);
            ctx.lineTo(rightPx, bottomPx - radius);
            ctx.quadraticCurveTo(rightPx, bottomPx, rightPx - radius, bottomPx);
            ctx.lineTo(leftPx + radius, bottomPx);
            ctx.quadraticCurveTo(leftPx, bottomPx, leftPx, bottomPx - radius);
            ctx.lineTo(leftPx, topPx + radius);
            ctx.quadraticCurveTo(leftPx, topPx, leftPx + radius, topPx);
            ctx.closePath();
            ctx.fill();
        }

        canvas.onclick = (event) => {
            if (!selectedCell) {
                alert('Sélectionnez d\'abord une cellule dans le tableau à corriger.');
                return;
            }

            const rect = canvas.getBoundingClientRect();
            const clickX = (event.clientX - rect.left) / zoomLevel;
            const clickY = (event.clientY - rect.top) / zoomLevel;
            console.log(`Clic détecté sur canvas à position ajustée : x=${clickX}, y=${clickY}`);

            let clickedToken = null;
            for (const tok of tokens) {  // Vérifier tous les tokens
                const leftPx = (tok.x0 / pdfWidth) * logicalWidth;
                const rightPx = (tok.x1 / pdfWidth) * logicalWidth;
                const topPx = (tok.y0 / pdfHeight) * logicalHeight;
                const bottomPx = (tok.y1 / pdfHeight) * logicalHeight;
                console.log(`Vérification du token ${tok.id} : bbox [left=${leftPx}, right=${rightPx}, top=${topPx}, bottom=${bottomPx}]`);

                if (clickX >= leftPx && clickX <= rightPx && clickY >= topPx && clickY <= bottomPx) {
                    clickedToken = tok;
                    console.log(`Token cliqué détecté : ID=${tok.id}, text="${tok.text}"`);
                    break;
                }
            }

            if (clickedToken) {
                const newId = String(clickedToken.id);
                // Vérifier si déjà assigné ailleurs et le libérer
                if (selectedIds.has(newId)) {
                    for (let r = 0; r < tableData.length; r++) {
                        for (let c of ['compte', 'solde_an', 'solde', 'débit', 'crédit']) {
                            if (tableData[r][c] && String(tableData[r][c][1]) === newId) {
                                const def = c === 'solde_an' ? 'N/A' : '0';
                                tableData[r][c] = [def, null];
                                console.log(`Libéré l'ancienne assignation pour ID ${newId} à la ligne ${r}, colonne ${c}`);
                                break;
                            }
                        }
                    }
                }

                const { rowIdx, col } = selectedCell;
                const def = col === 'solde_an' ? 'N/A' : '0';
                tableData[rowIdx][col] = [clickedToken.text || def, newId];
                console.log(`Cellule mise à jour : row=${rowIdx}, col=${col} avec valeur="${clickedToken.text}" et ID=${newId}`);
                
                updateSelectedIds();
                renderTable();
                highlightedId = newId;
                drawImage(pageIdx);
                selectedCell = null;
            } else {
                console.log('Aucun token cliqué ou clic en dehors des bboxes.');
            }
        };
    };
    img.onerror = () => {
        console.log('Erreur de chargement de l\'image');
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.fillStyle = 'gray';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        ctx.fillStyle = 'white';
        ctx.font = '20px Arial';
        ctx.textAlign = 'center';
        ctx.fillText('Image non disponible', canvas.width / 2, canvas.height / 2);
    };
}

// Surligner une cellule sélectionnée manuellement
function highlightCell() {
    const rowIdx = document.getElementById('row-select').value;
    const colIdx = parseInt(document.getElementById('col-select').value.split('_')[0]);
    if (rowIdx >= 0 && rowIdx < tableData.length) {
        const dataKey = colToDataKey[colIdx];
        const selectedId = tableData[rowIdx][dataKey] ? tableData[rowIdx][dataKey][1] : null;
        if (selectedId != null) {
            highlightedId = selectedId;
            drawImage(document.getElementById('page-select').value);
        } else {
            alert('Aucun ID associé à cette cellule.');
        }
    }
}

// Sauvegarder le tableau corrigé et envoyer à l'API
async function saveCorrectedTable() {
    if (!originalFilename) {
        alert('Aucun fichier original chargé.');
        return;
    }

    if (!documentId) {
        console.error('Aucun documentId disponible pour l\'envoi à l\'API.');
        alert('Erreur : ID du document manquant. Veuillez recharger le fichier.');
        return;
    }

    console.log(`Tentative d\'envoi des corrections avec documentId : ${documentId}`);

    // Préparer les données pour l'API
    const payload = {
        documentId: documentId,
        finalData: tableData
    };

    try {
        console.log('Envoi des données à /correct avec payload :', payload);
        const response = await fetch('http://localhost:5001/correct', {
            method: 'PATCH',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        });

        const result = await response.json();
        console.log('Réponse de l\'API /correct :', result);

        if (response.ok) {
            alert('Corrections envoyées avec succès !');
        } else {
            console.error('Échec de l\'envoi des corrections :', result.error);
            alert('Erreur lors de l\'envoi des corrections : ' + (result.error || 'Statut HTTP ' + response.status));
        }
    } catch (error) {
        console.error('Erreur lors de l\'appel à l\'API /correct :', error);
        alert('Une erreur est survenue lors de l\'envoi des corrections.');
    }

    // Sauvegarde locale (comportement existant)
    const correctedData = JSON.stringify(tableData, null, 2);
    const blob = new Blob([correctedData], { type: 'application/json' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${originalFilename}_corrected.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
    console.log(`Tableau sauvegardé localement dans ${originalFilename}_corrected.json`);
}

// Gérer le zoom
function handleZoom(direction) {
    if (direction === 'in') {
        zoomLevel = Math.min(zoomLevel + zoomStep, maxZoom);
    } else if (direction === 'out') {
        zoomLevel = Math.max(zoomLevel - zoomStep, minZoom);
    }
    console.log(`Niveau de zoom mis à jour : ${zoomLevel}`);
    drawImage(document.getElementById('page-select').value);
}

// Lancer l'extraction au chargement
window.onload = () => {
    const uploadBtn = document.getElementById('upload-btn');
    const extractBtn = document.getElementById('extract-btn');
    const fileInput = document.getElementById('pdf-upload');
    const pageSelect = document.getElementById('page-select');
    const dropZone = document.getElementById('drop-zone');
    const closePopupBtn = document.getElementById('close-popup');
    const validateBtn = document.getElementById('validate-btn');
    const checkFormulaBtn = document.getElementById('check-formula-btn');
    const zoomInBtn = document.getElementById('zoom-in-btn');
    const zoomOutBtn = document.getElementById('zoom-out-btn');

    uploadBtn.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', handleUpload);
    extractBtn.addEventListener('click', extractData);
    pageSelect.addEventListener('change', () => drawImage(pageSelect.value));
    dropZone.addEventListener('dragover', handleDragAndDrop);
    dropZone.addEventListener('dragleave', handleDragAndDrop);
    dropZone.addEventListener('drop', handleDragAndDrop);
    closePopupBtn.addEventListener('click', () => {
        document.getElementById('progress-popup').classList.add('hidden');
    });
    validateBtn.addEventListener('click', saveCorrectedTable);
    checkFormulaBtn.addEventListener('click', checkBalanceFormula);
    zoomInBtn.addEventListener('click', () => handleZoom('in'));
    zoomOutBtn.addEventListener('click', () => handleZoom('out'));
};