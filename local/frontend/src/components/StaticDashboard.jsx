import React, { useState, useMemo } from 'react';
import Plot from 'react-plotly.js';
import { kinematics, ANGLE_KEYS } from '../utils/kinematics';
import './StaticDashboard.css';

const PLOT_COLOR_MAP = {'Knee':'#2ecc71','Hip':'#2ecc71','Shoulder':'#3498db','Elbow':'#3498db','Neck':'#9b59b6','Torso':'#9b59b6','Waist':'#9b59b6','default':'#333333'};
const getPlotColor = (key) => { for (const part in PLOT_COLOR_MAP) { if (key.includes(part)) return PLOT_COLOR_MAP[part]; } return PLOT_COLOR_MAP['default']; };

// --- Configuration for Activity Detection ---
// You can tune these values to match your data
const MOVING_AVERAGE_WINDOW = 25; // Window size (in frames) for smoothing. 25-30 is a good start for 30fps video.
const ACTIVITY_THRESHOLD = 30;    // The smoothed score needed to be "active". You will need to re-tune this.
const MIN_ACTIVE_FRAMES = 15;     // The minimum number of consecutive active frames to count as a region.

function StaticDashboard() {
  const [kinematicData, setKinematicData] = useState(null);
  const [fileName, setFileName] = useState('');
  const [totalFrames, setTotalFrames] = useState(0);
  
  // State for activity detection results
  const [rawActivityScore, setRawActivityScore] = useState([]);
  const [smoothedActivityScore, setSmoothedActivityScore] = useState([]);
  const [activeRegions, setActiveRegions] = useState([]);

  const handleFileUpload = (event) => {
    const file = event.target.files[0];
    if (file && file.type === 'application/json') {
      setFileName(file.name);
      const reader = new FileReader();
      reader.onload = (e) => {
        const data = JSON.parse(e.target.result);
        const frameCount = data.length;
        setTotalFrames(frameCount);

        // 1. Process angles
        const allAngleData = ANGLE_KEYS.reduce((acc, key) => ({ ...acc, [key]: [] }), {});
        data.forEach(frame => {
          const keypoints = frame.predictions?.[0]?.keypoints;
          const angles = kinematics.process_all_angles(keypoints);
          ANGLE_KEYS.forEach(key => allAngleData[key].push(parseFloat(angles[key])));
        });
        setKinematicData(allAngleData);

        // --- IMPROVED: Activity Detection Logic with Smoothing ---

        // 2. Calculate Raw Activity Score (same as before)
        const majorJointKeys = ANGLE_KEYS.filter(k => k.includes('Hip') || k.includes('Knee') || k.includes('Shoulder') || k.includes('Elbow'));
        const rawScore = Array(frameCount).fill(0);
        for (let i = 1; i < frameCount; i++) {
            majorJointKeys.forEach(key => {
                rawScore[i] += Math.abs(allAngleData[key][i] - allAngleData[key][i-1]);
            });
        }
        setRawActivityScore(rawScore);

        // 3. Calculate Smoothed Activity Score using a Moving Average
        const halfWindow = Math.floor(MOVING_AVERAGE_WINDOW / 2);
        const smoothedScore = [];
        for (let i = 0; i < frameCount; i++) {
            const start = Math.max(0, i - halfWindow);
            const end = Math.min(frameCount - 1, i + halfWindow);
            let sum = 0;
            for (let j = start; j <= end; j++) {
                sum += rawScore[j];
            }
            smoothedScore[i] = sum / (end - start + 1);
        }
        setSmoothedActivityScore(smoothedScore);

        // 4. Identify active regions from the SMOOTHED score
        const regions = [];
        let startFrame = -1;
        for (let i = 0; i < frameCount; i++) {
            if (smoothedScore[i] > ACTIVITY_THRESHOLD && startFrame === -1) {
                startFrame = i;
            } else if (smoothedScore[i] <= ACTIVITY_THRESHOLD && startFrame !== -1) {
                if (i - startFrame >= MIN_ACTIVE_FRAMES) {
                    regions.push({ start: startFrame, end: i });
                }
                startFrame = -1;
            }
        }
        if (startFrame !== -1 && frameCount - startFrame >= MIN_ACTIVE_FRAMES) {
            regions.push({ start: startFrame, end: frameCount - 1 });
        }
        setActiveRegions(regions);
      };
      reader.readAsText(file);
    }
  };
  
  const x_axis_frames = useMemo(() => Array.from({ length: totalFrames }, (_, i) => i), [totalFrames]);
  
  const activityShapes = useMemo(() => {
    return activeRegions.map(region => ({
      type: 'rect', xref: 'x', yref: 'paper', x0: region.start, y0: 0, x1: region.end, y1: 1,
      fillcolor: '#3498db', opacity: 0.15, line: { width: 0 }
    }));
  }, [activeRegions]);

  const rightSideKeys = ANGLE_KEYS.filter(key => key.startsWith('R ') || key.startsWith('R_') || key.startsWith('Neck') );
  const leftSideAndCoreKeys = ANGLE_KEYS.filter(key => !rightSideKeys.includes(key));

  return (
    <div className="static-dashboard-layout">
      <header className="static-dashboard-header">
        <h1>Static Session Report</h1>
        <div className="static-session-selector">
          <div className="static-session-id-display">
            Session: <strong>{fileName ? fileName.split('.')[0] : 'N/A'}</strong>
          </div>
          <label htmlFor="static-file-upload" className="static-upload-button">Upload Session</label>
          <input type="file" accept=".json" onChange={handleFileUpload} id="static-file-upload" style={{ display: 'none' }} />
        </div>
      </header>

      {kinematicData ? (
        <div className="static-content-grid">
          {/* Activity Score Plot */}
          <div className="static-card" style={{ gridColumn: '1 / -1' }}>
            <h4>Overall Activity Score</h4>
            <Plot
              data={[
                { x: x_axis_frames, y: rawActivityScore, name: 'Raw Score', type: 'scatter', mode: 'lines', line: { color: '#bdc3c7', width: 1 } },
                { x: x_axis_frames, y: smoothedActivityScore, name: 'Smoothed Score', type: 'scatter', mode: 'lines', line: { color: '#e74c3c', width: 2.5 } }
              ]}
              layout={{
                title: { text: 'Total Body Movement (Smoothed)', font: { size: 11, color: '#4A5568' } },
                shapes: [ ...activityShapes, {
                    type: 'line', xref: 'paper', yref: 'y', x0: 0, y0: ACTIVITY_THRESHOLD, x1: 1, y1: ACTIVITY_THRESHOLD,
                    line: { color: 'rgba(0, 0, 0, 0.6)', width: 2, dash: 'dash' }, name: 'Threshold'
                }],
                legend: { x: 1, xanchor: 'right', y: 1 },
                margin: { l: 40, r: 10, b: 30, t: 40 },
                xaxis: { title: 'Frame' }, yaxis: { title: 'Activity Score' }
              }}
              config={{ displayModeBar: false }}
              style={{ width: '100%', height: '250px' }}
            />
          </div>

          {/* Left Column */}
          <div className="static-card">
            <h4>Core & Left Side</h4>
            <div className="static-charts-container">
              {leftSideAndCoreKeys.map(key => (
                <Plot key={key} data={[{ x: x_axis_frames, y: kinematicData[key], type: 'scatter', mode: 'lines', line: { color: getPlotColor(key), width: 2 } }]}
                  layout={{ title: { text: key, font: { size: 11, color: '#4A5568' } }, margin: { l: 40, r: 10, b: 30, t: 40 }, xaxis: { gridcolor: '#e2e8f0' }, yaxis: { range: key.includes('Bend') ? [0, 180] : [-180, 180], gridcolor: '#e2e8f0' }, shapes: activityShapes }}
                  config={{ displayModeBar: true, displaylogo: false, modeBarButtonsToRemove: ['zoomIn2d', 'zoomOut2d'] }}
                  style={{ width: '100%', height: '220px' }}/>
              ))}
            </div>
          </div>

          {/* Right Column */}
          <div className="static-card">
            <h4>Right Side</h4>
            <div className="static-charts-container">
              {rightSideKeys.map(key => (
                <Plot key={key} data={[{ x: x_axis_frames, y: kinematicData[key], type: 'scatter', mode: 'lines', line: { color: getPlotColor(key), width: 2 } }]}
                  layout={{ title: { text: key, font: { size: 11, color: '#4A5568' } }, margin: { l: 40, r: 10, b: 30, t: 40 }, xaxis: { gridcolor: '#e2e8f0' }, yaxis: { range: key.includes('Bend') ? [0, 180] : [-180, 180], gridcolor: '#e2e8f0' }, shapes: activityShapes }}
                  config={{ displayModeBar: true, displaylogo: false, modeBarButtonsToRemove: ['zoomIn2d', 'zoomOut2d'] }}
                  style={{ width: '100%', height: '220px' }}/>
              ))}
            </div>
          </div>
        </div>
      ) : (
        <div className="static-placeholder">
          <h2>Upload a session file to view the full report.</h2>
        </div>
      )}
    </div>
  );
}

export default StaticDashboard;