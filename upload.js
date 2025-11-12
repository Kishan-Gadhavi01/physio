// Use ES Module syntax for Node environment with "type": "module"
import 'dotenv/config'; // Loads .env file
import { MongoClient } from 'mongodb';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import crypto from 'crypto'; // For generating unique IDs

// --- ES MODULE SETUP FOR __dirname ---
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// --- CONFIGURATION ---
const MONGODB_URI = 'mongodb+srv://kishan:AYOijv3gEjKBYKFi@cloud.cc8illh.mongodb.net/?appName=cloud';
const DATABASE_NAME = "physio";
const FILES_DIR = path.join(__dirname, 'data_files'); 
// Set chunk size limit (e.g., 500 KB) to stay safely below the 16 MB BSON limit.
const MAX_CHUNK_SIZE_BYTES = 15000 * 1024; 
// ---------------------

async function uploadFiles() {
    if (!MONGODB_URI) {
        console.error("FATAL: MONGODB_URI is not defined. Check your .env file.");
        return;
    }

    let client;
    try {
        client = new MongoClient(MONGODB_URI);
        await client.connect();
        const db = client.db(DATABASE_NAME);
        
        const fileNames = fs.readdirSync(FILES_DIR);
        
        console.log(`Found ${fileNames.length} files in ${FILES_DIR}.`);

        // --- Process and Insert Files ---
        for (const fileName of fileNames) {
            if (path.extname(fileName) !== '.txt') {
                console.warn(`Skipping non-text file: ${fileName}`);
                continue;
            }

            const filePath = path.join(FILES_DIR, fileName);
            // Read file content as string
            const rawFileContent = fs.readFileSync(filePath, 'utf8');
            const lines = rawFileContent.split('\n');
            const sessionId = crypto.randomBytes(16).toString('hex');
            const totalLines = lines.length;
            const insertTime = Date.now();

            let collectionName;
            let dataFieldName;

            if (fileName.includes('angles')) {
                collectionName = 'angles';
                dataFieldName = 'angle_data_text';
            } else if (fileName.includes('pose')) {
                collectionName = 'pose';
                dataFieldName = 'vicon_data_text';
            } else {
                console.warn(`Skipping file ${fileName}: Cannot determine collection type.`);
                continue;
            }

            console.log(`\nProcessing file: ${fileName} (Session ID: ${sessionId})`);

            // --- 1. Chunking Logic ---
            let currentChunkLines = [];
            let currentChunkSize = 0;
            let chunkIndex = 0;
            const collection = db.collection(collectionName);
            
            for (const line of lines) {
                // Approximate size check
                const lineSize = Buffer.byteLength(line, 'utf8') + 1; // +1 for the newline character
                
                if (currentChunkSize + lineSize > MAX_CHUNK_SIZE_BYTES && currentChunkLines.length > 0) {
                    // Time to insert the current chunk
                    const chunkData = currentChunkLines.join('\n');
                    
                    const chunkDoc = {
                        sessionId: sessionId,
                        index: chunkIndex,
                        timestamp: insertTime,
                        [dataFieldName]: chunkData,
                    };
                    await collection.insertOne(chunkDoc);
                    process.stdout.write(`.`);
                    
                    // Reset for the next chunk
                    currentChunkLines = [];
                    currentChunkSize = 0;
                    chunkIndex++;
                }

                currentChunkLines.push(line);
                currentChunkSize += lineSize;
            }

            // --- 2. Insert the final (or only) chunk ---
            if (currentChunkLines.length > 0) {
                const chunkData = currentChunkLines.join('\n');
                const chunkDoc = {
                    sessionId: sessionId,
                    index: chunkIndex,
                    timestamp: insertTime,
                    [dataFieldName]: chunkData,
                };
                await collection.insertOne(chunkDoc);
                process.stdout.write(`.`);
                chunkIndex++;
            }
            
            // --- 3. Store Metadata (The "Header" document for the dropdown) ---
            const totalChunks = chunkIndex;
            const metadataDoc = {
                // Use the sessionId as the main ID for the frontend dropdown
                _id: sessionId, 
                name: fileName,
                timestamp: insertTime,
                totalChunks: totalChunks,
                totalLines: totalLines,
                // These fields must be null/empty, as the data is chunked
                angle_data_text: null, 
                vicon_data_text: null,
            };
            // Insert metadata into the same collection
            await collection.insertOne(metadataDoc);
            console.log(`\n[${collectionName}] File ${fileName} inserted into ${totalChunks + 1} documents.`);
        }
        
        console.log("\n\n✅ Batch Upload Complete!");

    } catch (error) {
        console.error("\n--- FATAL UPLOAD ERROR ---");
        console.error(error);
    } finally {
        if (client) {
            await client.close();
            console.log("Connection closed.");
        }
    }
}

uploadFiles();