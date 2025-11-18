import React from 'react';
import './PlaybackControls.css';

// Receive the new onClear prop
function PlaybackControls({ isPlaying, setIsPlaying, currentFrame, setCurrentFrame, totalFrames, onClear }) {
  return (
    <>
      <div className="button-group">
        <button onClick={() => setIsPlaying(!isPlaying)} className="play-button">
          {isPlaying ? 'Pause' : 'Play'}
        </button>
        {/* Add the Clear button, which calls the onClear function from props */}
        <button onClick={onClear} className="clear-button">
          Clear
        </button>
      </div>
      <input
        type="range"
        min="0"
        max={totalFrames}
        value={currentFrame}
        onChange={(e) => setCurrentFrame(Number(e.target.value))}
        className="timeline-slider"
      />
      <span className="frame-counter">{currentFrame} / {totalFrames}</span>
    </>
  );
}

export default PlaybackControls;

