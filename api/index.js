// --- Vercel Production Deployment File (CommonJS format) ---
// This file MUST use require() and module.exports for Vercel compatibility.
// MONGODB_URI is pulled from Vercel Environment Variables.

const express = require('express');
const { MongoClient, ObjectId } = require('mongodb');
const cors = require('cors');
const path = require('path'); 

// Create an Express app
const app = express();

// --- Configuration ---
// MONGODB_URI is provided by Vercel Environment Variables
const MONGODB_URI = process.env.MONGODB_URI;

let db;

// Middleware
app.use(cors()); 
app.use(express.json()); 

// Function to connect to MongoDB
async function connectToDb() {
    if (db) return db;
    if (!MONGODB_URI) {
        throw new Error("MONGODB_URI is not defined in Vercel Environment Variables.");
    }
    try {
        const client = new MongoClient(MONGODB_URI);
        await client.connect();
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
app.get('/recent-analysis', async (req, res) => {
    try {
        const db = await connectToDb();
        
        // Filter: Fetch only documents that have the 'totalChunks' field defined.
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


// --- 2. Fetch Data Chunks Endpoint ---
app.get('data-chunks', async (req, res) => {
    const { session: sessionId, collection: collectionName } = req.query;
    
    if (!sessionId || !collectionName) {
        return res.status(400).json({ error: "Missing sessionId or collection parameter." });
    }
    if (collectionName !== 'angles' && collectionName !== 'pose') {
        return res.status(400).json({ error: "Invalid collection specified." });
    }

    try {
        const db = await connectToDb();
        const dataFieldName = (collectionName === 'angles') ? 'angle_data_text' : 'vicon_data_text';

        // Find all chunks belonging to the sessionId
        const chunks = await db.collection(collectionName)
            .find({ sessionId: sessionId })
            .project({ [dataFieldName]: 1, index: 1, _id: 0 }) 
            .sort({ index: 1 })
            .toArray();

        // Map the result to include the data field as a generic 'data' property
        const mappedChunks = chunks
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


// --- Handle root route (Serves the frontend bundle) ---
app.get('/', (req, res) => {
    // Correct pathing for a Serverless Function nested inside api/
    const staticPath = path.join(__dirname, '..', '..');
    res.sendFile(path.join(staticPath, 'index.html'));
});


// VERCEL REQUIRED EXPORT
module.exports = app;