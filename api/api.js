import 'dotenv/config';
import express from 'express';
import { MongoClient } from 'mongodb';
import cors from 'cors';
import serverless from 'serverless-http';
import fetch from 'node-fetch';
import FormData from 'form-data';

// --- Express Setup ---
const app = express();
app.use(cors());
app.use(express.json({ limit: '50mb' }));

// --- MongoDB Setup ---
const MONGODB_URI = process.env.MONGODB_URI;
let db;

async function connectToDb() {
  if (db) return db;
  if (!MONGODB_URI) throw new Error('MONGODB_URI is not defined.');
  try {
    const client = new MongoClient(MONGODB_URI);
    await client.connect();
    db = client.db('physio');
    console.log('✅ Connected to MongoDB');
    return db;
  } catch (error) {
    console.error('❌ MongoDB connection failed:', error);
    throw error;
  }
}

// Helper to format MongoDB ObjectId
const formatResult = (doc) => ({
  ...doc,
  _id: doc._id.toString()
});

// --- 1️⃣ Recent Analysis Endpoint ---
app.get('/api/recent-analysis', async (req, res) => {
  try {
    const db = await connectToDb();
    const filter = { totalChunks: { $exists: true } };

    const angles = await db
      .collection('angles')
      .find(filter)
      .sort({ timestamp: -1 })
      .limit(5)
      .toArray();

    const poses = await db
      .collection('pose')
      .find(filter)
      .sort({ timestamp: -1 })
      .limit(5)
      .toArray();

    res.status(200).json({
      angles: angles.map(formatResult),
      poses: poses.map(formatResult)
    });
  } catch (error) {
    console.error('Error fetching recent analysis:', error);
    res.status(500).json({ error: 'Failed to fetch recent analysis metadata.' });
  }
});

// --- 2️⃣ Data Chunks Endpoint ---
app.get('/api/data-chunks', async (req, res) => {
  const { session: sessionId, collection: collectionName } = req.query;

  if (!sessionId || !collectionName)
    return res.status(400).json({ error: 'Missing sessionId or collection parameter.' });

  if (!['angles', 'pose'].includes(collectionName))
    return res.status(400).json({ error: 'Invalid collection specified.' });

  try {
    const db = await connectToDb();
    const dataField = collectionName === 'angles' ? 'angle_data_text' : 'vicon_data_text';

    const chunks = await db
      .collection(collectionName)
      .find({ sessionId })
      .project({ [dataField]: 1, index: 1, _id: 0 })
      .sort({ index: 1 })
      .toArray();

    const formatted = chunks
      .filter((c) => c[dataField])
      .map((c) => ({ index: c.index, data: c[dataField] }));

    res.status(200).json(formatted);
  } catch (error) {
    console.error('Error fetching data chunks:', error);
    res.status(500).json({ error: 'Failed to fetch data chunks.' });
  }
});

// --- 3️⃣ Proxy to External Analyzer API ---
app.post('/api/analyze', async (req, res) => {
  try {
    // Collect raw body from client
    const chunks = [];
    req.on('data', (chunk) => chunks.push(chunk));
    req.on('end', async () => {
      const buffer = Buffer.concat(chunks);

      // Prepare FormData to forward to external analyzer
      const form = new FormData();
      form.append('file', buffer, 'input.txt');

      // Forward to your external analyzer
      const response = await fetch('http://3.232.209.122/analyze-session/', {
        method: 'POST',
        body: form
      });

      if (!response.ok) {
        const text = await response.text();
        console.error('Analyzer error:', text);
        return res.status(response.status).send(text);
      }

      const data = await response.json();
      res.status(200).json(data);
    });
  } catch (error) {
    console.error('Proxy /api/analyze failed:', error);
    res.status(500).json({ error: 'Proxy to analyzer failed', details: error.message });
  }
});

// --- Export for Vercel ---
export const handler = serverless(app);
export default app;
