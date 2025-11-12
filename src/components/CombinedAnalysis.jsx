import React, { useState, useEffect, useCallback } from 'react';
import Plot from 'react-plotly.js';

// --- ABSOLUTE URL DEFINITION ---
const LOCAL_API_HOST = 'http://localhost:3000'; 

// API endpoints
const INTERNAL_API_URL = LOCAL_API_HOST + '/api/recent-analysis';
const CHUNK_API_URL = (sessionId, collection) => LOCAL_API_HOST + `/api/data-chunks?session=${sessionId}&collection=${collection}`; 
const ANALYSIS_API_URL = "http://3.232.209.122/analyze-session/";

// --- NEW FUNCTION: Fetch and reassemble data chunks ---
const fetchAndReassembleChunks = async (sessionId, collectionName) => {
    const url = CHUNK_API_URL(sessionId, collectionName);
    
    // NOTE: This fetch call now uses the absolute URL defined above
    const response = await fetch(url);
    
    if (!response.ok) {
        throw new Error(`Failed to fetch data chunks. Status: ${response.status}`);
    }
    const chunks = await response.json();
    
    // Check if the server returned an error or if the chunks array is empty
    if (!Array.isArray(chunks) || chunks.length === 0) {
        throw new Error("No data chunks found for this session ID.");
    }

    // Sort chunks by index and join the data string
    // The 'data' property holds the raw text field content (angle_data_text or vicon_data_text)
    const reassembledText = chunks
        .sort((a, b) => a.index - b.index)
        .map(chunk => chunk.data)
        .join('\n'); 
        
    return reassembledText;
};


// Helper function to safely parse Vicon/Pose data (Restored)
const parseViconData = (text) => {
    const lines = text.trim().split('\n');
    if (lines.length === 0 || lines[0].trim() === "") throw new Error("File/Data is empty.");
    const frame_step = 5;
    const all_x = [], all_y = [], all_z = [], frameIndices = [];
    
    for (let i = 0; i < lines.length; i++) {
        if (i % frame_step !== 0) continue;
        const parts = lines[i].trim().split(/[\s,]+/);
        const coords = parts.map(Number);
        if (coords.some(isNaN) || coords.length === 0) continue;
        if (coords.length % 3 !== 0) throw new Error(`Invalid data shape (cols: ${coords.length}).`);
        
        const frame_x = [], frame_y = [], frame_z = [];
        for (let j = 0; j < coords.length; j += 3) {
            frame_x.push(coords[j]); frame_y.push(coords[j + 1]); frame_z.push(coords[j + 2]);
        }
        all_x.push(frame_x); all_y.push(frame_y); all_z.push(frame_z); frameIndices.push(i);
    }
    
    if (all_x.length === 0) throw new Error("No valid data frames parsed.");
    
    return { all_x, all_y, all_z, frameIndices };
};


function CombinedAnalysis() {
    // --- State for Data Source Dropdowns ---
    const [recentData, setRecentData] = useState({ angles: [], poses: [] });
    const [selectedAngleId, setSelectedAngleId] = useState('');
    const [selectedPoseId, setSelectedPoseId] = useState('');
    const [dataLoadingError, setDataLoadingError] = useState(null);

    // --- State for 3D Vicon Plotly ---
    const [plotData, setPlotData] = useState([]);
    const [plotLayout, setPlotLayout] = useState({});
    const [plotFrames, setPlotFrames] = useState([]);
    const [viconFileName, setViconFileName] = useState('');
    const [viconError, setViconError] = useState(null);
    
    // --- State for Angle Analysis ---
    const [analysisResult, setAnalysisResult] = useState(null);
    const [isLoadingAnalysis, setIsLoadingAnalysis] = useState(false);
    const [analysisError, setAnalysisError] = useState(null);

    // --- EFFECT: Load recent data on component mount (Restored) ---
    useEffect(() => {
        const fetchRecentData = async () => {
            try {
                // Fetch header/metadata documents only using the absolute URL
                const response = await fetch(INTERNAL_API_URL);
                if (!response.ok) {
                    const errorData = await response.json().catch(() => ({ error: `HTTP status ${response.status}` }));
                    throw new Error(`Failed to fetch recent data. Server responded with: ${errorData.error || response.statusText}`);
                }
                const data = await response.json();
                console.log("Fetched Header Data:", data);
                setRecentData(data);
            } catch (err) {
                console.error("Failed to fetch recent data:", err);
                setDataLoadingError(`Failed to load data: ${err.message}. Ensure backend is running on ${LOCAL_API_HOST}.`);
            }
        };
        fetchRecentData();
    }, []); 

    // --- HANDLER: Visualize Pose Data (3D Plot - Restored) ---
    const visualizePose = useCallback(async (poseObject) => {
        setViconError(null);
        setPlotData([]); setPlotLayout({}); setPlotFrames([]);
        setViconFileName(poseObject.name || `Session ID: ${poseObject._id}`);
        setAnalysisResult(null); // Clear previous analysis
        
        try {
            // STEP 1: Fetch and reassemble the raw text data from chunks
            const viconTextData = await fetchAndReassembleChunks(poseObject._id, 'pose');
            
            if (!viconTextData) {
                setViconError("Visualization data not found.");
                return;
            }
            
            // STEP 2: Parse the reassembled text data
            const { all_x, all_y, all_z, frameIndices } = parseViconData(viconTextData);

            // STEP 3: Construct Plotly elements (Core plotting logic)
            const firstFrameData = [{
                x: all_x[0], y: all_y[0], z: all_z[0],
                type: 'scatter3d', mode: 'markers',
                marker: { size: 5, color: all_z[0], colorscale: 'Viridis' }
            }];
            const newFrames = all_x.map((x_coords, k) => ({
                name: `Frame ${frameIndices[k]}`,
                data: [{ x: x_coords, y: all_y[k], z: all_z[k] }]
            }));
            const newLayout = {
                title: `3D Position Animation: ${poseObject.name || poseObject._id}`,
                margin: { l: 0, r: 0, b: 0, t: 40 },
                scene: { aspectmode: 'data', xaxis: {title: 'X'}, yaxis: {title: 'Y'}, zaxis: {title: 'Z'} },
                updatemenus: [{
                    type: 'buttons', showactive: false, x: 0.1, y: 0,
                    buttons: [
                        { label: 'Play', method: 'animate', args: [null, { frame: { duration: 30, redraw: true }, fromcurrent: true, transition: { duration: 0 } }] },
                        { label: 'Pause', method: 'animate', args: [[null], { mode: 'immediate', frame: { duration: 0, redraw: true }, transition: { duration: 0 } }] }
                    ]
                }],
                sliders: [{
                    active: 0, pad: { t: 50, b: 10 }, currentvalue: { visible: true, prefix: 'Frame: ' },
                    steps: frameIndices.map((frameIndex, k) => ({
                        label: frameIndex.toString(), method: 'animate',
                        args: [[`Frame ${frameIndex}`], { mode: 'immediate', frame: { duration: 30, redraw: true }, transition: { duration: 0 } }]
                    }))
                }]
            };

            setPlotData(firstFrameData); setPlotFrames(newFrames); setPlotLayout(newLayout);

        } catch (err) {
            setViconError(`Visualization Error: ${err.message}`);
        }
    }, []);

    // --- HANDLER: Analyze Angle Data (Restored) ---
    const analyzeAngle = useCallback(async (angleObject) => {
        setIsLoadingAnalysis(true);
        setAnalysisResult(null); setAnalysisError(null);
        setPlotData([]); setPlotLayout({}); setPlotFrames([]); // Clear 3D plot

        try {
            // STEP 1: Fetch and reassemble the raw text data from chunks
            const angleTextData = await fetchAndReassembleChunks(angleObject._id, 'angles');

            if (!angleTextData) {
                setAnalysisError("Analysis data not found.");
                setIsLoadingAnalysis(false);
                return;
            }

            // STEP 2: Create a Blob from the reassembled string to simulate file upload
            const file = new Blob([angleTextData], { type: 'text/plain' });
            const formData = new FormData();
            formData.append('file', file, angleObject.name || `${angleObject._id}.txt`);

            // STEP 3: Send to external analyzer API (remains the same)
            const response = await fetch(ANALYSIS_API_URL, { 
                method: 'POST', 
                body: formData 
            });

            if (!response.ok) {
                const errData = await response.json().catch(() => ({ detail: `HTTP status ${response.status}` }));
                throw new Error(errData.detail || `HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            setAnalysisResult(data);
        } catch (err) {
            console.error("Analysis Error:", err);
            setAnalysisError(err.message);
        } finally {
            setIsLoadingAnalysis(false);
        }
    }, []);

    // --- HANDLER: Dropdown Change for Pose (Restored) ---
    const handlePoseChange = (event) => {
        const id = event.target.value;
        setSelectedPoseId(id);
        if (id) {
            const selectedPose = recentData.poses.find(p => p._id === id);
            if (selectedPose) {
                visualizePose(selectedPose); 
            }
        } else {
            setPlotData([]); setPlotLayout({}); setPlotFrames([]);
            setViconFileName(''); setViconError(null);
        }
    };

    // --- HANDLER: Dropdown Change for Angle (Restored) ---
    const handleAngleChange = (event) => {
        const id = event.target.value;
        setSelectedAngleId(id);
        if (id) {
            const selectedAngle = recentData.angles.find(a => a._id === id);
            if (selectedAngle) {
                analyzeAngle(selectedAngle);
            }
        } else {
            setAnalysisResult(null); setAnalysisError(null);
        }
    };


    // Helper to format dropdown options
    const formatOptionName = (doc, index) => {
        const date = doc.timestamp ? new Date(doc.timestamp).toLocaleString() : `Item ${index + 1}`;
        return `${doc.name || doc._id} (${date})`;
    };

    // --- Render Logic (UI structure remains the same) ---
    return (
        <div className="dashboard-layout">
            <header className="dashboard-header">
                <h1>Combined Analysis</h1>
            </header>

            <div className="content-grid">
                
                {/* --- Top-Left: Controls (Now Dropdowns) --- */}
                <div className="card controls-container">
                    {dataLoadingError && <p style={{ color: 'red' }}>{dataLoadingError}</p>}

                    <strong>Vicon Playback (Pose Data)</strong>
                    <select 
                        value={selectedPoseId} 
                        onChange={handlePoseChange} 
                        className="upload-button" 
                        style={{ width: '100%', marginTop: '5px' }}
                        disabled={isLoadingAnalysis}
                    >
                        <option value="">-- Select Recent Pose Data --</option>
                        {recentData.poses.map((pose, index) => (
                            <option key={pose._id} value={pose._id}>
                                {formatOptionName(pose, index)}
                            </option>
                        ))}
                    </select>

                    <div className="session-id-display" style={{ color: viconError ? 'red' : 'inherit', height: '20px' }}>
                        {viconError ? viconError : viconFileName}
                    </div>

                    <hr style={{width: '100%', margin: '15px 0'}} />

                    <strong>Angle Analysis</strong>
                    <select 
                        value={selectedAngleId} 
                        onChange={handleAngleChange} 
                        className="upload-button" 
                        style={{ width: '100%', marginTop: '5px' }}
                        disabled={isLoadingAnalysis}
                    >
                        <option value="">-- Select Recent Angle Data --</option>
                        {recentData.angles.map((angle, index) => (
                            <option key={angle._id} value={angle._id}>
                                {formatOptionName(angle, index)}
                            </option>
                        ))}
                    </select>

                    <div className="session-id-display" style={{ color: analysisError ? 'red' : 'inherit', height: '20px' }}>
                        {analysisError ? analysisError : (analysisResult ? analysisResult.fileName : '')}
                    </div>
                </div>
                
                {/* --- Bottom-Left: The 3D Plot (RESTORED) --- */}
                <div className="card three-container" style={{ padding: 0, overflow: 'hidden' }}>
                    {!plotData.length && !isLoadingAnalysis && (
                        <div className="placeholder">Select Pose Data for 3D playback.</div>
                    )}
                    {isLoadingAnalysis && !analysisResult && (
                        <div className="placeholder">Loading...</div>
                    )}
                    {plotData.length > 0 && (
                        <Plot
                            data={plotData}
                            layout={plotLayout}
                            frames={plotFrames}
                            config={{ responsive: true, displayModeBar: true, scrollZoom: true }}
                            style={{ width: '100%', height: '100%' }}
                        />
                    )}
                </div>

                {/* --- Bottom-Right: Analysis Chart 2 + Summary (Unchanged Logic) --- */}
                <div className="vertical-content-stack" style={{ width: '100%', padding: '0 10px' }}>

                    {!plotData.length && !analysisResult && (
                    <div className="card" style={{ width: 'calc(100% - 20px)', margin: '10px' }}>
                        <div className="placeholder">
                        {isLoadingAnalysis ? 'Loading...' : 'Select a data source to begin analysis or visualization.'}
                        </div>
                    </div>
                    )}

                    {analysisResult && (  
                    <>
                        <div className="card" style={{ width: 'calc(200% - 20px)', height: '600px', padding: 0, overflow: 'hidden', margin: '10px' }}>
                            <iframe
                                title="Analysis Plot 1"
                                srcDoc={analysisResult.plot_html_1}
                                style={{ width: '100%', height: '100%', border: 'none' }}
                            />
                        </div>
                        
                        <div className="card" style={{ width: 'calc(200% - 20px)', height: '600px', padding: 0, overflow: 'hidden', margin: '10px' }}>
                            <iframe
                                title="Analysis Plot 2"
                                srcDoc={analysisResult.plot_html_2}
                                style={{ width: '100%', height: '100%', border: 'none' }}
                            />
                        </div>

                        <div className="card" style={{ width: 'calc(200% - 20px)', height: '600px', padding: 0, overflow: 'hidden', margin: '10px' }}>
                            <strong style={{textAlign: 'center', display: 'block'}}>Summary</strong>
                            <div className="summary-table-container" style={{ paddingTop: '10px', overflowY: 'auto' }}>
                                <table style={{width: '90%', margin: '0 auto', borderCollapse: 'collapse'}}>
                                    <tbody>
                                        <tr style={{borderBottom: '1px solid var(--border-color)'}}>
                                            <td style={{padding: '4px', fontWeight: 'bold'}}>File</td>
                                            <td style={{padding: '4px', textAlign: 'right'}}>{analysisResult.fileName}</td>
                                        </tr>
                                        {analysisResult.summary.map((line, index) => {
                                            const parts = line.split(': ');
                                            const metric = parts[0] || "Status";
                                            const value = parts[1] || (parts[0] ? '' : line);
                                            return (
                                                <tr key={index} style={{borderBottom: '1px solid var(--border-color)'}}>
                                                    <td style={{padding: '4px', fontWeight: 'bold'}}>{metric}</td>
                                                    <td style={{padding: '4px', textAlign: 'right'}}>{value}</td>
                                                </tr>
                                            );
                                        })}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </>
                    )}
                </div>
            </div>
        </div>
    );
}

export default CombinedAnalysis;