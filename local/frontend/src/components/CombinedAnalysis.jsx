import React, { useState, useCallback } from 'react';
import Plot from 'react-plotly.js';

// --- API HOST DEFINITION ---
const LOCAL_API_HOST = 'http://127.0.0.1:8001'; 
const ANALYSIS_API_URL = LOCAL_API_HOST + "/analyze-session/";

// --- Helper function to safely parse Vicon/Pose data (Restored and adapted) ---
const parseViconData = (text) => {
    // This logic is restored from your initial component
    const lines = text.trim().split('\n');
    if (lines.length === 0 || lines[0].trim() === "") throw new Error("File/Data is empty.");
    // Assuming the file uses a step of 5 frames for animation data, as in your original component
    const frame_step = 5; 
    const all_x = [], all_y = [], all_z = [], frameIndices = [];
    
    for (let i = 0; i < lines.length; i++) {
        if (i % frame_step !== 0) continue;
        // Use a regex to split by one or more spaces or commas
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
    // --- State for 3D Vicon Plotly ---
    const [plotData, setPlotData] = useState([]);
    const [plotLayout, setPlotLayout] = useState({});
    const [plotFrames, setPlotFrames] = useState([]);
    const [viconFileName, setViconFileName] = useState('');
    const [viconError, setViconError] = useState(null);
    const [isViconLoading, setIsViconLoading] = useState(false);
    
    // --- State for Angle Analysis ---
    const [analysisResult, setAnalysisResult] = useState(null);
    const [isLoadingAnalysis, setIsLoadingAnalysis] = useState(false);
    const [analysisError, setAnalysisError] = useState(null);
    const [angleFileName, setAngleFileName] = useState('');

    // --- HANDLER: Pose Visualization File Upload (ACTIVE LOGIC) ---
    const handlePoseUpload = useCallback(async (event) => {
        const file = event.target.files[0];
        setViconError(null);
        setPlotData([]); setPlotLayout({}); setPlotFrames([]);
        
        if (!file) {
            setViconError("No pose file selected.");
            setViconFileName('');
            return;
        }

        setIsViconLoading(true);
        setViconFileName(file.name);
        
        const reader = new FileReader();
        reader.onload = async (e) => {
            try {
                const viconTextData = e.target.result;
                
                // STEP 1: Parse the text data using the restored logic
                const { all_x, all_y, all_z, frameIndices } = parseViconData(viconTextData);

                // STEP 2: Construct Plotly elements (Restored Plotly setup)
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
                    title: `3D Position Animation: ${file.name}`,
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
                setPlotData([]);
            } finally {
                setIsViconLoading(false);
                event.target.value = null; // Clear input
            }
        };

        reader.onerror = () => {
            setViconError("Failed to read file.");
            setIsViconLoading(false);
            event.target.value = null; // Clear input
        };

        reader.readAsText(file);
    }, []);

    // --- HANDLER: Angle Analysis File Upload (ACTIVE LOGIC) ---
    const handleAngleUpload = useCallback(async (event) => {
        const file = event.target.files[0];
        if (!file) {
            setAnalysisError("No angle file selected.");
            return;
        }

        setIsLoadingAnalysis(true);
        setAnalysisResult(null); 
        setAnalysisError(null);
        setAngleFileName(file.name);

        try {
            // STEP 1: Create FormData object
            const formData = new FormData();
            formData.append('file', file, file.name);

            // STEP 2: Send to local analyzer API
            const response = await fetch(ANALYSIS_API_URL, { 
                method: 'POST', 
                body: formData 
            });

            if (!response.ok) {
                const errorText = await response.text();
                let detailMessage = `HTTP error! Status: ${response.status}`;
                try {
                    const errData = JSON.parse(errorText);
                    detailMessage = errData.detail || detailMessage;
                } catch {
                    if (errorText.length < 200) detailMessage += ` - ${errorText}`; 
                }
                throw new Error(detailMessage);
            }

            const data = await response.json();
            setAnalysisResult(data);
        } catch (err) {
            console.error("Analysis Error:", err);
            setAnalysisError(`Analysis Failed: ${err.message}`);
        } finally {
            setIsLoadingAnalysis(false);
            event.target.value = null; // Clear input
        }
    }, []);


    // --- Render Logic (UI structure remains the same) ---
    return (
        <div className="dashboard-layout">
            <header className="dashboard-header">
                <h1>Combined Analysis</h1>
            </header>

            <div className="content-grid">
                
                {/* --- Top-Left: Controls (File Uploads replacing Dropdowns) --- */}
                <div className="card controls-container">
                    
                    {/* Vicon Playback Section (File Input) */}
                    <strong>Vicon Playback (Pose Data)</strong>
                    <input 
                        type="file" 
                        accept=".txt,.csv" 
                        onChange={handlePoseUpload} 
                        className="upload-button" 
                        style={{ width: '100%', marginTop: '5px' }}
                        disabled={isViconLoading || isLoadingAnalysis}
                    />

                    <div className="session-id-display" style={{ color: viconError ? 'red' : 'inherit', height: '20px' }}>
                        {isViconLoading ? 'Loading Vicon...' : viconError ? viconError : viconFileName}
                    </div>

                    <hr style={{width: '100%', margin: '15px 0'}} />

                    {/* Angle Analysis Section (File Input) */}
                    <strong>Angle Analysis</strong>
                    <input 
                        type="file" 
                        accept=".txt,.csv" 
                        onChange={handleAngleUpload} 
                        className="upload-button" 
                        style={{ width: '100%', marginTop: '5px' }}
                        disabled={isLoadingAnalysis || isViconLoading}
                    />

                    <div className="session-id-display" style={{ color: analysisError ? 'red' : 'inherit', height: '20px' }}>
                        {isLoadingAnalysis ? 'Processing Analysis...' : analysisError ? analysisError : (analysisResult ? analysisResult.fileName : angleFileName)}
                    </div>
                </div>
                
                {/* --- Bottom-Left: The 3D Plot (ACTIVE) --- */}
                <div className="card three-container" style={{ padding: 0, overflow: 'hidden' }}>
                    {(!plotData.length && !isViconLoading && !isLoadingAnalysis) && (
                        <div className="placeholder">Upload Pose Data for 3D playback.</div>
                    )}
                    {(isViconLoading || isLoadingAnalysis) && (
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

                {/* --- Right Column: Analysis Charts and Summary (EXACTLY THE SAME) --- */}
                <div className="vertical-content-stack" style={{ width: '100%', padding: '0 10px' }}>

                    {!analysisResult && ( 
                    <div className="card" style={{ width: 'calc(100% - 20px)', margin: '10px' }}>
                        <div className="placeholder">
                        {isLoadingAnalysis ? 'Loading...' : 'Upload Angle Analysis file to see results.'}
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