import React, { useState, useRef, useEffect } from 'react';
// --- FIX: Corrected import paths ---
// Assuming TrackMe.jsx is in src/components/
// and the other components are also in src/components/
// and kinematics.js is in src/utils/
import Skeleton3DViewer from './Skeleton3DViewer';
import KinematicsGraphs from './KinematicsGraphs';
import { ANGLE_KEYS } from '../utils/kinematics';

// We can reuse the same CSS as the playback dashboard
import './Dashboard.css';
// -----------------------------------

// WebSocket URL from your Python API
const WEBSOCKET_URL = "ws://127.0.0.1:8000/ws/pose";

function TrackMe() {
  const [isConnected, setIsConnected] = useState(false);
  const [allFrames, setAllFrames] = useState([]); // Stores all received frame data
  const [allAngleData, setAllAngleData] = useState(() => 
    ANGLE_KEYS.reduce((acc, key) => ({ ...acc, [key]: [] }), {})
  );
  const [currentKeypoints, setCurrentKeypoints] = useState([]);
  const ws = useRef(null); // Ref to hold the WebSocket object

  // Split keys for graph columns, just like in Dashboard.jsx
  const rightSideKeys = ANGLE_KEYS.filter(key => key.startsWith('R ') || key.startsWith('R_') || key.startsWith('Neck') );
  const leftSideAndCoreKeys = ANGLE_KEYS.filter(key => !rightSideKeys.includes(key));

  // Effect to clean up WebSocket on component unmount
  useEffect(() => {
    // This function is returned from useEffect and acts as a cleanup
    return () => {
      if (ws.current && ws.current.readyState === WebSocket.OPEN) {
        ws.current.close();
      }
    };
  }, []);

  const handleStartStop = () => {
    if (isConnected) {
      // --- STOP STREAM ---
      if (ws.current) {
        ws.current.close();
      }
    } else {
      // --- START STREAM ---
      // Clear old data
      setAllFrames([]);
      setAllAngleData(ANGLE_KEYS.reduce((acc, key) => ({ ...acc, [key]: [] }), {}));
      setCurrentKeypoints([]);

      // Connect to WebSocket
      ws.current = new WebSocket(WEBSOCKET_URL);

      ws.current.onopen = () => {
        console.log("WebSocket connected");
        setIsConnected(true);
      };

      ws.current.onclose = () => {
        console.log("WebSocket disconnected");
        setIsConnected(false);
        ws.current = null;
      };

      ws.current.onerror = (error) => {
        console.error("WebSocket Error:", error);
      };

      ws.current.onmessage = (event) => {
        const frameData = JSON.parse(event.data);
        console.log(frameData)

        // 1. Update live 3D skeleton
        const keypoints = frameData.predictions?.[0]?.keypoints || [];
        setCurrentKeypoints(keypoints);

        // 2. Accumulate data for the graphs
        setAllFrames(prevFrames => [...prevFrames, frameData]);
        
        // --- FIX: Update state immutably ---
        // This forces React to detect the change by creating new arrays
        // instead of mutating old ones.
        setAllAngleData(prevData => {
          const newData = {}; // Create a brand new object
          for (const key of ANGLE_KEYS) {
            // For each key, create a new array by copying the old one
            // and adding the new value.
            newData[key] = [...(prevData[key] || []), frameData.angles[key] || 0];
          }
          //console.log(newData)
          return newData; // Return the new object
        });
        
        // -----------------------------------
      };
    }
  };

  return (
    <div className="dashboard-layout">
      <header className="dashboard-header">
        <h1>Track Me (Live)</h1>
        <div className="session-selector">
          <div className="session-id-display">
            Status: <strong>{isConnected ? "Connected" : "Disconnected"}</strong>
          </div>
          {/* This button starts and stops the live feed */}
          <button 
            onClick={handleStartStop} 
            className={`upload-button ${isConnected ? 'stop-button' : ''}`}
          >
            {isConnected ? 'Stop Session' : 'Start Session'}
          </button>
        </div>
      </header>

      <div className="content-grid">
        <div className="card controls-container">
          {/* Status/Control Box */}
          <div className="placeholder">
            {isConnected ? `Streaming... Frames: ${allFrames.length}` : "Click 'Start Session' to connect."}
          </div>
        </div>
          
        <div className="card three-container">
          <Skeleton3DViewer keypoints={currentKeypoints} />
        </div>

        <div className="card charts-column">
          <KinematicsGraphs
            title="Core & Left Side"
            data={allAngleData}
            frames={allFrames}
            currentFrame={allFrames.length - 1} // Always show the latest frame
            keysToShow={leftSideAndCoreKeys}
          />
        </div>
        <div className="card charts-column">
          <KinematicsGraphs
            title="Right Side"
            data={allAngleData}
            frames={allFrames}
            currentFrame={allFrames.length - 1} // Always show the latest frame
            keysToShow={rightSideKeys}
          />
        </div>
      </div>
    </div>
  );
}

export default TrackMe;