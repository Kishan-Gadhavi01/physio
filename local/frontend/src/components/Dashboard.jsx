import React, { useState, useEffect, useRef, useMemo } from 'react';
import PlaybackControls from './PlaybackControls';
import Skeleton3DViewer from './Skeleton3DViewer';
import KinematicsGraphs from './KinematicsGraphs';
import { kinematics, ANGLE_KEYS } from '../utils/kinematics';

import './Dashboard.css';

function Dashboard() {
  const [frames, setFrames] = useState([]);
  const [kinematicData, setKinematicData] = useState({});
  const [currentFrame, setCurrentFrame] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [fileName, setFileName] = useState('');
  const animationRef = useRef();

  const handleFileUpload = (event) => {
    // ... same as before
    const file = event.target.files[0];
    if (file && file.type === 'application/json') {
      setFileName(file.name);
      const reader = new FileReader();
      reader.onload = (e) => {
        const data = JSON.parse(e.target.result);
        setFrames(data);
        const allAngleData = ANGLE_KEYS.reduce((acc, key) => ({ ...acc, [key]: [] }), {});
        data.forEach(frame => {
          const keypoints = frame.predictions?.[0]?.keypoints;
          const angles = kinematics.process_all_angles(keypoints);
          ANGLE_KEYS.forEach(key => {
            allAngleData[key].push(parseFloat(angles[key]));
          });
        });
        setKinematicData(allAngleData);
        setCurrentFrame(0);
        setIsPlaying(false);
      };
      reader.readAsText(file);
      event.target.value = null; // Allow re-uploading the same file
    }
  };

  // --- NEW: Function to clear all session data ---
  const handleClear = () => {
    setFrames([]);
    setKinematicData({});
    setCurrentFrame(0);
    setIsPlaying(false);
    setFileName('');
  };

  useEffect(() => {
    // ... same as before
    if (isPlaying && frames.length > 0) {
      animationRef.current = setInterval(() => {
        setCurrentFrame(prev => (prev + 1) % frames.length);
      }, 100);
    } else {
      clearInterval(animationRef.current);
    }
    return () => clearInterval(animationRef.current);
  }, [isPlaying, frames.length]);

  const currentKeypoints = frames[currentFrame]?.predictions?.[0]?.keypoints || [];
  const rightSideKeys = ANGLE_KEYS.filter(key => key.startsWith('R ') || key.startsWith('R_') || key.startsWith('Neck') );
  const leftSideAndCoreKeys = ANGLE_KEYS.filter(key => !rightSideKeys.includes(key));
  return (
    <div className="dashboard-layout">
      <header className="dashboard-header">
        <h1>Session Analysis</h1>
        <div className="session-selector">
          <div className="session-id-display">
            Session: <strong>{fileName ? fileName.split('.')[0] : 'N/A'}</strong>
          </div>
          <label htmlFor="file-upload" className="upload-button">Upload New Session</label>
          <input type="file" accept=".json" onChange={handleFileUpload} id="file-upload" style={{ display: 'none' }} />
        </div>
      </header>

      <div className="content-grid">
        <div className="card controls-container">
          {frames.length > 0 ? (
            <PlaybackControls
              isPlaying={isPlaying}
              setIsPlaying={setIsPlaying}
              currentFrame={currentFrame}
              setCurrentFrame={setCurrentFrame}
              totalFrames={frames.length - 1}
              onClear={handleClear} // Pass the clear function as a prop
            />
          ) : (
            <div className="placeholder">Upload a session to enable playback.</div>
          )}
        </div>
          
        {/* The rest of the JSX is unchanged... */}
        <div className="card three-container">
          <Skeleton3DViewer keypoints={currentKeypoints} />
        </div>
        <div className="card charts-column">
          <KinematicsGraphs
            title="Core & Left Side"
            data={kinematicData}
            frames={frames}
            currentFrame={currentFrame}
            keysToShow={leftSideAndCoreKeys}
          />
        </div>
        <div className="card charts-column">
          <KinematicsGraphs
            title="Right Side"
            data={kinematicData}
            frames={frames}
            currentFrame={currentFrame}
            keysToShow={rightSideKeys}
          />
        </div>
      </div>
    </div>
  );
}

export default Dashboard;

