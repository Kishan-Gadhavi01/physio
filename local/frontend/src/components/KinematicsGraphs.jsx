import React, { useMemo } from 'react';
import Plot from 'react-plotly.js';
import './KinematicsGraphs.css';

const PLOT_COLOR_MAP = {'Knee':'#2ecc71','Hip':'#2ecc71','Shoulder':'#3498db','Elbow':'#3498db','Neck':'#9b59b6','Torso':'#9b59b6','Waist':'#9b59b6','default':'#333333'};
const getPlotColor = (key) => { for (const part in PLOT_COLOR_MAP) { if (key.includes(part)) return PLOT_COLOR_MAP[part]; } return PLOT_COLOR_MAP['default']; };


function KinematicsGraphs({ title, data, frames, currentFrame, keysToShow }) {
  const x_axis_frames = useMemo(() => Array.from({ length: frames.length }, (_, i) => i), [frames.length]);

  if (frames.length === 0) {
    return <div className="placeholder">Graphs will appear here.</div>;
  }

  return (
    <>
      <h4>{title}</h4>
      <div className="charts-container">
        {keysToShow.map(key => (
          <Plot
            key={key}
            data={[{
              x: x_axis_frames.slice(0, currentFrame + 1),
              y: data[key] ? data[key].slice(0, currentFrame + 1) : [],
              type: 'scatter',
              mode: 'lines',
              line: { color: getPlotColor(key), width: 2 }
            }]}
            layout={{
              title: { text: key, font: { size: 11, color: '#4A5568' } },
              margin: { l: 40, r: 10, b: 30, t: 40 },
              xaxis: { range: [0, frames.length - 1], gridcolor: '#e2e8f0' },
              yaxis: { range: key.includes('Bend') ? [0, 180] : [-180, 180], gridcolor: '#e2e8f0' },
              paper_bgcolor: '#ffffff',
              plot_bgcolor: '#ffffff'
            }}
config={{ displayModeBar: true,  displaylogo: false, modeBarButtonsToRemove: [
    'zoomIn2d',    // The "Zoom in" button
    'zoomOut2d'    // The "Zoom out" button
  ]}}            style={{ width: '100%', height: '220px' }}
          />
        ))}
      </div>
    </>
  );
}

export default KinematicsGraphs;
