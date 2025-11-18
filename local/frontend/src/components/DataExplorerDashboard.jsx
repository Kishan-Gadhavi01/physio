import React, { useState, useMemo } from 'react';
import Plot from 'react-plotly.js';
import { getGroupedJoints } from './constants'; // Import from the new constants file
import './StaticDashboard.css'; // You can reuse your existing CSS

// --- Main React Component ---
function DataExplorerDashboard() {
  const [angleData, setAngleData] = useState(null);
  const [fileName, setFileName] = useState('');
  const [totalFrames, setTotalFrames] = useState(0);

  /**
   * Handles the upload and parsing of UI-PRMD .txt data files.
   */
  const handleFileUpload = (event) => {
    const file = event.target.files[0];
    if (file) {
      setFileName(file.name);
      const reader = new FileReader();
      reader.onload = (e) => {
        const text = e.target.result;
        // 1. Parse the space-separated text file into a 2D array of numbers
        const dataMatrix = text.trim().split('\n').map(line =>
          line.trim().split(/\s+/).map(Number)
        );

        if (dataMatrix.length === 0 || dataMatrix[0].length !== 117) {
            alert("Error: The file does not seem to be a valid UI-PRMD Vicon angles file. Expected 117 columns of data.");
            return;
        }

        const frameCount = dataMatrix.length;
        setTotalFrames(frameCount);

        // 2. Transpose the matrix so we have one array per angle channel
        const transposed = dataMatrix[0].map((_, colIndex) =>
          dataMatrix.map(row => row[colIndex])
        );

        // 3. Map the transposed data to our named angles
        const allAngleData = {};
        const angleKeys = getGroupedJoints();
        const flatKeys = Object.values(angleKeys).flat();
        
        let colIdx = 0;
        flatKeys.forEach(jointName => {
            allAngleData[`${jointName}_Y`] = transposed[colIdx++];
            allAngleData[`${jointName}_X`] = transposed[colIdx++];
            allAngleData[`${jointName}_Z`] = transposed[colIdx++];
        });
        
        setAngleData(allAngleData);
      };
      reader.readAsText(file);
    }
  };

  const groupedJoints = useMemo(() => getGroupedJoints(), []);
  const x_axis_frames = useMemo(() => Array.from({ length: totalFrames }, (_, i) => i), [totalFrames]);
  const yxz_colors = ['#3498db', '#e74c3c', '#2ecc71']; // Colors for Y, X, Z

  return (
    <div className="static-dashboard-layout">
      <header className="static-dashboard-header">
        <h1>UI-PRMD Session Report</h1>
        <div className="static-session-selector">
          <div className="static-session-id-display">
            Session: <strong>{fileName ? fileName.split('.')[0] : 'N/A'}</strong>
          </div>
          <label htmlFor="static-file-upload" className="static-upload-button">Upload Session (.txt)</label>
          <input type="file" accept=".txt" onChange={handleFileUpload} id="static-file-upload" style={{ display: 'none' }} />
        </div>
      </header>

      {angleData ? (
        <div className="ui-prmd-content-grid">
          {Object.entries(groupedJoints).map(([groupName, joints]) => (
            <div key={groupName} className="static-card">
              <h4>{groupName}</h4>
              <div className="static-charts-container">
                {joints.map(jointName => (
                  <Plot
                    key={jointName}
                    data={[
                      { x: x_axis_frames, y: angleData[`${jointName}_Y`], name: 'Y-axis', type: 'scatter', mode: 'lines', line: { color: yxz_colors[0], width: 1.5 } },
                      { x: x_axis_frames, y: angleData[`${jointName}_X`], name: 'X-axis', type: 'scatter', mode: 'lines', line: { color: yxz_colors[1], width: 1.5 } },
                      { x: x_axis_frames, y: angleData[`${jointName}_Z`], name: 'Z-axis', type: 'scatter', mode: 'lines', line: { color: yxz_colors[2], width: 1.5 } }
                    ]}
                    layout={{
                      title: { text: jointName, font: { size: 11, color: '#4A5568' } },
                      margin: { l: 40, r: 10, b: 30, t: 40 },
                      xaxis: { title: { text: 'Frame', standoff: 5 }, gridcolor: '#e2e8f0' },
                      yaxis: { title: { text: 'Degrees' }, gridcolor: '#e2e8f0', range: [-200, 200] },
                      legend: { x: 1, xanchor: 'right', y: 1 }
                    }}
                    config={{ displayModeBar: true, displaylogo: false, modeBarButtonsToRemove: ['zoomIn2d', 'zoomOut2d', 'pan2d', 'select2d', 'lasso2d'] }}
                    style={{ width: '100%', height: '220px' }}
                  />
                ))}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="static-placeholder">
          <h2>Upload a UI-PRMD Vicon angles file (.txt) to view the report.</h2>
        </div>
      )}
    </div>
  );
}

export default DataExplorerDashboard;