import 'dotenv/config';
import express from 'express';
import { MongoClient } from 'mongodb';
import cors from 'cors';
import serverless from 'serverless-http';

const app = express();
app.use(cors());
app.use(express.json());

const MONGODB_URI = process.env.MONGODB_URI;
let db;

async function connectToDb() {
  if (db) return db;
  const client = new MongoClient(MONGODB_URI);
  await client.connect();
  db = client.db('physio');
  return db;
}

// Helper
const formatResult = (doc) => ({ ...doc, _id: doc._id.toString() });

// --- 1. Recent Analysis ---
app.get('/api/recent-analysis', async (req, res) => {
  try {
    const db = await connectToDb();
    const filter = { totalChunks: { $exists: true } };
    const angles = await db.collection('angles').find(filter).sort({ timestamp: -1 }).limit(5).toArray();
    const poses = await db.collection('pose').find(filter).sort({ timestamp: -1 }).limit(5).toArray();
    res.status(200).json({ angles: angles.map(formatResult), poses: poses.map(formatResult) });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// --- 2. Data Chunks ---
app.get('/api/data-chunks', async (req, res) => {
  const { session: sessionId, collection: collectionName } = req.query;
  if (!sessionId || !collectionName) return res.status(400).json({ error: 'Missing parameters.' });

  const validCollections = ['angles', 'pose'];
  if (!validCollections.includes(collectionName))
    return res.status(400).json({ error: 'Invalid collection.' });

  try {
    const db = await connectToDb();
    const dataField = collectionName === 'angles' ? 'angle_data_text' : 'vicon_data_text';
    const chunks = await db.collection(collectionName)
      .find({ sessionId })
      .project({ [dataField]: 1, index: 1, _id: 0 })
      .sort({ index: 1 })
      .toArray();

    const formatted = chunks
      .filter(c => c[dataField])
      .map(c => ({ index: c.index, data: c[dataField] }));

    res.status(200).json(formatted);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Export handler for Vercel
export const handler = serverless(app);
export default app;
