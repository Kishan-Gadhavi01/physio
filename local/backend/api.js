// --- Note: dotenv/require is removed since MONGODB_URI is hardcoded below ---
require('dotenv').config();

const express = require('express');
const { MongoClient, ObjectId } = require('mongodb');
const cors = require('cors');
const path = require('path');

// Create an Express app
const app = express();

// --- Configuration ---
// Using the hardcoded URI provided by the user
const MONGODB_URI = process.env.MONGODB_URI;
const PORT = process.env.PORT || 3000;

let db;

// Middleware
app.use(cors()); // Allow cross-origin requests
app.use(express.json()); // Parse JSON bodies

// --- Serve static files (index.html) ---
const staticPath = path.join(__dirname, '..'); 
app.use(express.static(staticPath));

// Function to connect to MongoDB
async function connectToDb() {
    if (db) return db;
    if (!MONGODB_URI) {
        throw new Error("MONGODB_URI is not defined.");
    }
    try {
        const client = new MongoClient(MONGODB_URI);
        await client.connect();
        // Set DB name to 'physio' as defined in the user's file
        db = client.db("physio"); 
        console.log("Connected to MongoDB!");
        return db;
    } catch (error) {
        console.error("Failed to connect to MongoDB:", error);
        throw error;
    }
}

// Helper to convert ObjectId to string for JSON transport
const formatResult = (doc) => ({
    ...doc,
    _id: doc._id.toString()
});


// --- 1. Fetch Metadata (Dropdown List) Endpoint ---
app.get('/api/recent-analysis', async (req, res) => {
    try {
        const db = await connectToDb();
        
        // --- FIX: Filter for documents that have the 'totalChunks' field defined. ---
        // This ensures only the header/metadata document for each session is retrieved.
        const filter = { totalChunks: { $exists: true } };

        const angles = await db.collection('angles')
            .find(filter)
            .sort({ timestamp: -1 }) 
            .limit(5)
            .toArray();

        const poses = await db.collection('pose')
            .find(filter)
            .sort({ timestamp: -1 }) 
            .limit(5)
            .toArray();

        res.status(200).json({
            angles: angles.map(formatResult),
            poses: poses.map(formatResult)
        });
    } catch (error) {
        console.error("Error fetching recent analysis metadata:", error);
        res.status(500).json({ error: 'Failed to fetch recent analysis metadata from database' });
    }
});


// --- 2. Fetch Data Chunks Endpoint (Correct) ---
app.get('/api/data-chunks', async (req, res) => {
    // SessionId is the _id from the metadata document selected by the user
    const { session: sessionId, collection: collectionName } = req.query;
    
    if (!sessionId || !collectionName) {
        return res.status(400).json({ error: "Missing sessionId or collection parameter." });
    }

    if (collectionName !== 'angles' && collectionName !== 'pose') {
        return res.status(400).json({ error: "Invalid collection specified." });
    }

    try {
        const db = await connectToDb();
        // Determine which data field to project based on the collection name
        const dataFieldName = (collectionName === 'angles') ? 'angle_data_text' : 'vicon_data_text';

        // Find all chunks belonging to the sessionId (stored as the sessionId field)
        const chunks = await db.collection(collectionName)
            .find({ sessionId: sessionId })
            // Project only the necessary fields and exclude the metadata header document
            .project({ [dataFieldName]: 1, index: 1, _id: 0 }) 
            // Sort by index to ensure correct reassembly order
            .sort({ index: 1 })
            .toArray();

        // Map the result to include the data field as a generic 'data' property
        const mappedChunks = chunks
             // Filter out the metadata header document if it was accidentally included
            .filter(chunk => chunk[dataFieldName] !== null) 
            .map(chunk => ({
                index: chunk.index,
                data: chunk[dataFieldName]
            }));

        res.status(200).json(mappedChunks);

    } catch (error) {
        console.error("Error fetching data chunks:", error);
        res.status(500).json({ error: 'Failed to fetch data chunks.' });
    }
});


// --- Handle root route ---
app.get('/', (req, res) => {
    res.sendFile(path.join(staticPath, 'index.html'));
});


// --- START THE LOCAL SERVER ---
app.listen(PORT, () => {
    console.log(`Server running locally on http://localhost:${PORT}`);
    console.log(`Metadata API: http://localhost:${PORT}/api/recent-analysis`);
});


// Export the app
module.exports = app;