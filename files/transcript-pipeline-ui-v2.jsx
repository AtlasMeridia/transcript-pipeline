import React, { useState, useEffect, useRef } from 'react';

// Waveform visualization component
const Waveform = ({ isActive, phase }) => {
  const canvasRef = useRef(null);
  const animationRef = useRef(null);
  const timeRef = useRef(0);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const width = canvas.width;
    const height = canvas.height;

    const draw = () => {
      timeRef.current += 0.02;
      ctx.fillStyle = 'rgba(10, 10, 8, 0.15)';
      ctx.fillRect(0, 0, width, height);

      if (isActive) {
        ctx.strokeStyle = phase === 'transcribing' ? '#E8A84C' : 
                          phase === 'extracting' ? '#4CE8A8' : '#E8A84C';
        ctx.lineWidth = 2;
        ctx.beginPath();

        for (let x = 0; x < width; x++) {
          const frequency = phase === 'transcribing' ? 0.03 : 0.02;
          const amplitude = phase === 'transcribing' ? 25 : 15;
          const noise = Math.sin(x * 0.1 + timeRef.current * 3) * 5;
          const y = height / 2 + 
                    Math.sin(x * frequency + timeRef.current * 2) * amplitude +
                    Math.sin(x * frequency * 2.5 + timeRef.current * 3) * (amplitude * 0.5) +
                    noise;
          
          if (x === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        }
        ctx.stroke();

        // Scanline effect
        const scanY = (timeRef.current * 50) % height;
        ctx.strokeStyle = 'rgba(232, 168, 76, 0.1)';
        ctx.beginPath();
        ctx.moveTo(0, scanY);
        ctx.lineTo(width, scanY);
        ctx.stroke();
      } else {
        // Flatline with subtle noise
        ctx.strokeStyle = 'rgba(232, 168, 76, 0.3)';
        ctx.lineWidth = 1;
        ctx.beginPath();
        for (let x = 0; x < width; x++) {
          const y = height / 2 + Math.random() * 2 - 1;
          if (x === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        }
        ctx.stroke();
      }

      animationRef.current = requestAnimationFrame(draw);
    };

    draw();
    return () => cancelAnimationFrame(animationRef.current);
  }, [isActive, phase]);

  return (
    <canvas 
      ref={canvasRef} 
      width={600} 
      height={80}
      style={{
        width: '100%',
        height: '80px',
        borderRadius: '2px',
        border: '1px solid rgba(232, 168, 76, 0.2)',
      }}
    />
  );
};

// Progress indicator with phase labels
const PhaseIndicator = ({ currentPhase, phases }) => {
  const phaseIndex = phases.indexOf(currentPhase);
  
  return (
    <div style={{
      display: 'flex',
      gap: '4px',
      alignItems: 'center',
      fontFamily: '"JetBrains Mono", monospace',
      fontSize: '11px',
      letterSpacing: '0.05em',
    }}>
      {phases.map((phase, i) => (
        <React.Fragment key={phase}>
          <span style={{
            color: i < phaseIndex ? '#4CE8A8' : 
                   i === phaseIndex ? '#E8A84C' : 
                   'rgba(232, 168, 76, 0.3)',
            textTransform: 'uppercase',
            transition: 'color 0.3s ease',
          }}>
            {i < phaseIndex ? '✓ ' : i === phaseIndex ? '► ' : '○ '}
            {phase}
          </span>
          {i < phases.length - 1 && (
            <span style={{ color: 'rgba(232, 168, 76, 0.2)' }}>—</span>
          )}
        </React.Fragment>
      ))}
    </div>
  );
};

// Log entry component
const LogEntry = ({ timestamp, message, type }) => (
  <div style={{
    fontFamily: '"JetBrains Mono", monospace',
    fontSize: '12px',
    lineHeight: '1.6',
    display: 'flex',
    gap: '12px',
    opacity: type === 'dim' ? 0.5 : 1,
  }}>
    <span style={{ color: 'rgba(232, 168, 76, 0.5)' }}>{timestamp}</span>
    <span style={{ 
      color: type === 'success' ? '#4CE8A8' : 
             type === 'error' ? '#E84C4C' :
             type === 'info' ? '#4C9EE8' :
             '#E8DCC8' 
    }}>
      {message}
    </span>
  </div>
);

// Result card component
const ResultCard = ({ title, type, content, isActive, onView }) => (
  <div style={{
    background: isActive ? 'rgba(232, 168, 76, 0.08)' : 'rgba(232, 168, 76, 0.03)',
    border: `1px solid ${isActive ? 'rgba(232, 168, 76, 0.4)' : 'rgba(232, 168, 76, 0.15)'}`,
    borderRadius: '4px',
    padding: '20px',
    transition: 'all 0.2s ease',
    cursor: 'pointer',
    position: 'relative',
  }}
  onMouseEnter={(e) => {
    if (!isActive) {
      e.currentTarget.style.background = 'rgba(232, 168, 76, 0.06)';
      e.currentTarget.style.borderColor = 'rgba(232, 168, 76, 0.3)';
    }
  }}
  onMouseLeave={(e) => {
    if (!isActive) {
      e.currentTarget.style.background = 'rgba(232, 168, 76, 0.03)';
      e.currentTarget.style.borderColor = 'rgba(232, 168, 76, 0.15)';
    }
  }}
  onClick={onView}
  >
    {isActive && (
      <div style={{
        position: 'absolute',
        top: '-1px',
        left: '20px',
        right: '20px',
        height: '2px',
        background: type === 'transcript' ? '#E8A84C' : '#4CE8A8',
        borderRadius: '0 0 2px 2px',
      }} />
    )}
    <div style={{
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'flex-start',
      marginBottom: '12px',
    }}>
      <div>
        <div style={{
          fontFamily: '"Instrument Serif", Georgia, serif',
          fontSize: '18px',
          color: '#E8DCC8',
          marginBottom: '4px',
        }}>
          {title}
        </div>
        <div style={{
          fontFamily: '"JetBrains Mono", monospace',
          fontSize: '10px',
          textTransform: 'uppercase',
          letterSpacing: '0.1em',
          color: type === 'transcript' ? '#E8A84C' : '#4CE8A8',
        }}>
          {type}
        </div>
      </div>
      <div style={{
        fontFamily: '"JetBrains Mono", monospace',
        fontSize: '11px',
        color: 'rgba(232, 168, 76, 0.5)',
      }}>
        .md {isActive ? '▼' : '↗'}
      </div>
    </div>
    <div style={{
      fontFamily: '"JetBrains Mono", monospace',
      fontSize: '11px',
      color: 'rgba(232, 168, 76, 0.6)',
      lineHeight: '1.5',
      overflow: 'hidden',
      textOverflow: 'ellipsis',
      display: '-webkit-box',
      WebkitLineClamp: 3,
      WebkitBoxOrient: 'vertical',
    }}>
      {content}
    </div>
  </div>
);

// Markdown Preview Pane
const MarkdownPreview = ({ type, title, content, metadata, onClose }) => {
  const [copied, setCopied] = useState(false);
  const isTranscript = type === 'transcript';

  const generateMarkdown = () => {
    const metaBlock = `# ${title}

**Author**: ${metadata.author}
**Date**: ${metadata.date}
**Duration**: ${metadata.duration}
**Processed**: ${metadata.processed}

---

`;
    return metaBlock + content;
  };

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(generateMarkdown());
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };
  
  // Parse transcript content to highlight timestamps
  const renderTranscript = (text) => {
    const lines = text.split('\n');
    return lines.map((line, i) => {
      const timestampMatch = line.match(/^\[(\d{2}:\d{2}:\d{2})\]\s*(.*)/);
      if (timestampMatch) {
        return (
          <div key={i} style={{
            display: 'flex',
            gap: '16px',
            marginBottom: '12px',
            lineHeight: '1.7',
          }}>
            <span style={{
              fontFamily: '"JetBrains Mono", monospace',
              fontSize: '12px',
              color: '#E8A84C',
              flexShrink: 0,
              opacity: 0.7,
            }}>
              {timestampMatch[1]}
            </span>
            <span style={{
              color: '#E8DCC8',
              fontFamily: '"Source Serif 4", Georgia, serif',
              fontSize: '15px',
            }}>
              {timestampMatch[2]}
            </span>
          </div>
        );
      }
      return line ? <p key={i} style={{ marginBottom: '12px' }}>{line}</p> : null;
    });
  };

  // Parse summary content with sections
  const renderSummary = (text) => {
    const sections = text.split(/(?=## )/);
    return sections.map((section, i) => {
      const headerMatch = section.match(/^## (.+)\n([\s\S]*)/);
      if (headerMatch) {
        const [, header, content] = headerMatch;
        const isBulletList = content.includes('- ');
        
        return (
          <div key={i} style={{ marginBottom: '32px' }}>
            <h3 style={{
              fontFamily: '"Instrument Serif", Georgia, serif',
              fontSize: '20px',
              fontWeight: '400',
              color: '#4CE8A8',
              marginBottom: '16px',
              paddingBottom: '8px',
              borderBottom: '1px solid rgba(76, 232, 168, 0.2)',
            }}>
              {header}
            </h3>
            {isBulletList ? (
              <ul style={{
                listStyle: 'none',
                padding: 0,
                margin: 0,
              }}>
                {content.split('\n').filter(l => l.startsWith('- ')).map((item, j) => (
                  <li key={j} style={{
                    fontFamily: '"Source Serif 4", Georgia, serif',
                    fontSize: '15px',
                    lineHeight: '1.7',
                    color: '#E8DCC8',
                    marginBottom: '8px',
                    paddingLeft: '20px',
                    position: 'relative',
                  }}>
                    <span style={{
                      position: 'absolute',
                      left: 0,
                      color: '#4CE8A8',
                    }}>›</span>
                    {item.slice(2)}
                  </li>
                ))}
              </ul>
            ) : (
              <p style={{
                fontFamily: '"Source Serif 4", Georgia, serif',
                fontSize: '15px',
                lineHeight: '1.8',
                color: '#E8DCC8',
              }}>
                {content.trim()}
              </p>
            )}
          </div>
        );
      }
      return section.trim() ? (
        <p key={i} style={{
          fontFamily: '"Source Serif 4", Georgia, serif',
          fontSize: '15px',
          lineHeight: '1.8',
          color: '#E8DCC8',
          marginBottom: '16px',
        }}>
          {section}
        </p>
      ) : null;
    });
  };

  return (
    <div style={{
      background: 'rgba(10, 10, 8, 0.98)',
      border: '1px solid rgba(232, 168, 76, 0.2)',
      borderRadius: '6px',
      marginTop: '16px',
      overflow: 'hidden',
      animation: 'slideDown 0.3s ease-out',
    }}>
      {/* Preview Header */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        padding: '16px 24px',
        borderBottom: '1px solid rgba(232, 168, 76, 0.1)',
        background: 'rgba(232, 168, 76, 0.03)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{
            fontFamily: '"JetBrains Mono", monospace',
            fontSize: '12px',
            color: isTranscript ? '#E8A84C' : '#4CE8A8',
            padding: '4px 10px',
            background: isTranscript ? 'rgba(232, 168, 76, 0.1)' : 'rgba(76, 232, 168, 0.1)',
            borderRadius: '3px',
          }}>
            {isTranscript ? 'TRANSCRIPT' : 'SUMMARY'}
          </div>
          <span style={{
            fontFamily: '"JetBrains Mono", monospace',
            fontSize: '12px',
            color: 'rgba(232, 168, 76, 0.5)',
          }}>
            {title.toLowerCase().replace(/\s+/g, '-')}-{type}.md
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <button
            onClick={handleCopy}
            style={{
              background: copied ? 'rgba(76, 232, 168, 0.2)' : 'rgba(232, 168, 76, 0.1)',
              border: `1px solid ${copied ? 'rgba(76, 232, 168, 0.3)' : 'rgba(232, 168, 76, 0.2)'}`,
              borderRadius: '4px',
              padding: '8px 16px',
              fontFamily: '"JetBrains Mono", monospace',
              fontSize: '11px',
              color: copied ? '#4CE8A8' : '#E8A84C',
              cursor: 'pointer',
              transition: 'all 0.2s ease',
              minWidth: '120px',
            }}
            onMouseEnter={(e) => {
              if (!copied) {
                e.target.style.background = 'rgba(232, 168, 76, 0.2)';
              }
            }}
            onMouseLeave={(e) => {
              if (!copied) {
                e.target.style.background = 'rgba(232, 168, 76, 0.1)';
              }
            }}
          >
            {copied ? '✓ Copied!' : '⎘ Copy .md'}
          </button>
          <button
            style={{
              background: 'rgba(232, 168, 76, 0.1)',
              border: '1px solid rgba(232, 168, 76, 0.2)',
              borderRadius: '4px',
              padding: '8px 16px',
              fontFamily: '"JetBrains Mono", monospace',
              fontSize: '11px',
              color: '#E8A84C',
              cursor: 'pointer',
              transition: 'all 0.2s ease',
            }}
            onMouseEnter={(e) => {
              e.target.style.background = 'rgba(232, 168, 76, 0.2)';
            }}
            onMouseLeave={(e) => {
              e.target.style.background = 'rgba(232, 168, 76, 0.1)';
            }}
          >
            ↓ Download .md
          </button>
          <button
            onClick={onClose}
            style={{
              background: 'transparent',
              border: 'none',
              padding: '8px',
              fontFamily: '"JetBrains Mono", monospace',
              fontSize: '16px',
              color: 'rgba(232, 168, 76, 0.5)',
              cursor: 'pointer',
              transition: 'color 0.2s ease',
            }}
            onMouseEnter={(e) => e.target.style.color = '#E8A84C'}
            onMouseLeave={(e) => e.target.style.color = 'rgba(232, 168, 76, 0.5)'}
          >
            ✕
          </button>
        </div>
      </div>

      {/* Metadata Bar */}
      <div style={{
        display: 'flex',
        gap: '24px',
        padding: '12px 24px',
        borderBottom: '1px solid rgba(232, 168, 76, 0.1)',
        background: 'rgba(232, 168, 76, 0.02)',
      }}>
        {Object.entries(metadata).map(([key, value]) => (
          <div key={key} style={{
            fontFamily: '"JetBrains Mono", monospace',
            fontSize: '11px',
          }}>
            <span style={{ color: 'rgba(232, 168, 76, 0.4)', marginRight: '8px' }}>
              {key}:
            </span>
            <span style={{ color: 'rgba(232, 168, 76, 0.8)' }}>
              {value}
            </span>
          </div>
        ))}
      </div>

      {/* Content Area */}
      <div style={{
        padding: '32px',
        maxHeight: '500px',
        overflowY: 'auto',
      }}>
        {/* Document Title */}
        <h1 style={{
          fontFamily: '"Instrument Serif", Georgia, serif',
          fontSize: '32px',
          fontWeight: '400',
          color: '#E8DCC8',
          marginBottom: '8px',
          letterSpacing: '-0.02em',
        }}>
          {title}
        </h1>
        
        {isTranscript && (
          <div style={{
            fontFamily: '"JetBrains Mono", monospace',
            fontSize: '11px',
            color: 'rgba(232, 168, 76, 0.5)',
            marginBottom: '32px',
          }}>
            Full transcript with timestamps
          </div>
        )}

        {!isTranscript && (
          <div style={{
            fontFamily: '"JetBrains Mono", monospace',
            fontSize: '11px',
            color: 'rgba(76, 232, 168, 0.5)',
            marginBottom: '32px',
          }}>
            AI-extracted insights and key points
          </div>
        )}

        <div style={{
          borderTop: '1px solid rgba(232, 168, 76, 0.1)',
          paddingTop: '24px',
        }}>
          {isTranscript ? renderTranscript(content) : renderSummary(content)}
        </div>
      </div>

      {/* Preview Footer */}
      <div style={{
        padding: '12px 24px',
        borderTop: '1px solid rgba(232, 168, 76, 0.1)',
        background: 'rgba(232, 168, 76, 0.02)',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
      }}>
        <span style={{
          fontFamily: '"JetBrains Mono", monospace',
          fontSize: '10px',
          color: 'rgba(232, 168, 76, 0.4)',
        }}>
          {isTranscript ? '4,892 words • 24m 18s' : 'Generated by Claude Sonnet 4.5'}
        </span>
        <span style={{
          fontFamily: '"JetBrains Mono", monospace',
          fontSize: '10px',
          color: 'rgba(232, 168, 76, 0.4)',
        }}>
          Scroll for more ↓
        </span>
      </div>
    </div>
  );
};

// Main application
export default function TranscriptPipeline() {
  const [url, setUrl] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [currentPhase, setCurrentPhase] = useState(null);
  const [logs, setLogs] = useState([]);
  const [results, setResults] = useState(null);
  const [showResults, setShowResults] = useState(false);
  const [activePreview, setActivePreview] = useState(null); // 'transcript' | 'summary' | null

  const phases = ['download', 'transcribing', 'extracting', 'complete'];

  const addLog = (message, type = 'default') => {
    const now = new Date();
    const timestamp = now.toTimeString().slice(0, 8);
    setLogs(prev => [...prev, { timestamp, message, type }]);
  };

  // Sample content for preview
  const sampleTranscript = `[00:00:00] Welcome to this deep dive into transformer architecture. Today we're going to explore one of the most influential innovations in modern AI.

[00:00:15] The transformer was introduced in the famous paper "Attention Is All You Need" by Vaswani et al. in 2017, and it completely revolutionized how we approach sequence-to-sequence tasks.

[00:00:42] Before transformers, we relied heavily on recurrent neural networks, or RNNs, and their variants like LSTMs and GRUs. These had a fundamental limitation: they processed sequences one step at a time.

[00:01:15] The key innovation of the transformer is the self-attention mechanism. Instead of processing tokens sequentially, self-attention allows the model to look at all positions in the input simultaneously.

[00:01:48] Let me explain how self-attention works with a concrete example. Consider the sentence "The animal didn't cross the street because it was too tired."

[00:02:20] When processing the word "it", the model needs to understand what "it" refers to. Self-attention computes attention scores between "it" and every other word in the sentence.

[00:02:55] The attention mechanism uses three learned projections: queries, keys, and values. The query represents what we're looking for, keys represent what each position offers, and values contain the actual information.

[00:03:30] Another crucial component is positional encoding. Since attention is permutation-invariant, we need to inject position information explicitly into the model.

[00:04:05] The original transformer uses sinusoidal positional encodings, though modern variants often use learned position embeddings or relative positional encodings like RoPE.

[00:04:42] Multi-head attention is another key innovation. Instead of computing attention once, we compute it multiple times in parallel with different learned projections.

[00:05:18] This allows the model to attend to information from different representation subspaces at different positions, capturing various types of relationships.`;

  const sampleSummary = `## Executive Summary

This video provides a comprehensive introduction to transformer architecture, the foundational technology behind modern large language models like GPT-4 and Claude. The presenter explains the key innovations that made transformers revolutionary: self-attention mechanisms, positional encodings, and multi-head attention.

## Key Points

- Transformers replaced sequential RNN processing with parallel self-attention, dramatically improving training efficiency
- The self-attention mechanism computes relationships between all positions simultaneously, enabling better long-range dependency modeling
- Query-Key-Value projections form the mathematical foundation of attention computation
- Positional encodings are necessary because attention is inherently position-agnostic
- Multi-head attention allows models to capture different types of relationships in parallel

## Technical Concepts Explained

- Self-attention: A mechanism that relates different positions of a sequence to compute representations
- Positional encoding: Signals added to embeddings to convey sequence order information
- Multi-head attention: Running multiple attention operations in parallel with different learned projections
- Query/Key/Value: The three projections used in attention computation

## Notable Quotes

- "Attention is all you need - that phrase perfectly captures the paradigm shift transformers represent"
- "The ability to look at all positions simultaneously is what gives transformers their power"

## Actionable Insights

- Understanding attention mechanisms is foundational for working with any modern LLM
- When debugging transformer behavior, examining attention patterns can reveal what the model is "looking at"
- The principles of transformers extend beyond NLP to vision, audio, and multimodal applications`;

  const simulateProcessing = async () => {
    if (!url.trim()) return;
    
    setIsProcessing(true);
    setLogs([]);
    setResults(null);
    setShowResults(false);
    setActivePreview(null);

    // Download phase
    setCurrentPhase('download');
    addLog('Initializing pipeline...', 'dim');
    await new Promise(r => setTimeout(r, 500));
    addLog(`Fetching video metadata from ${url.slice(0, 50)}...`);
    await new Promise(r => setTimeout(r, 1200));
    addLog('Video found: "Understanding Transformer Architecture"', 'info');
    addLog('Duration: 24m 18s | Channel: AI Explained', 'dim');
    await new Promise(r => setTimeout(r, 800));
    addLog('Downloading audio stream...', 'info');
    await new Promise(r => setTimeout(r, 1500));
    addLog('Audio downloaded successfully (48.2 MB)', 'success');

    // Transcribe phase
    setCurrentPhase('transcribing');
    await new Promise(r => setTimeout(r, 400));
    addLog('Streaming to ElevenLabs Scribe v2...', 'info');
    await new Promise(r => setTimeout(r, 2000));
    addLog('Transcription in progress...', 'dim');
    await new Promise(r => setTimeout(r, 2500));
    addLog('Processing timestamps...', 'dim');
    await new Promise(r => setTimeout(r, 1000));
    addLog('Transcription complete (4,892 words)', 'success');

    // Extract phase
    setCurrentPhase('extracting');
    await new Promise(r => setTimeout(r, 400));
    addLog('Sending to Claude for extraction...', 'info');
    await new Promise(r => setTimeout(r, 1800));
    addLog('Analyzing content structure...', 'dim');
    await new Promise(r => setTimeout(r, 1500));
    addLog('Generating executive summary...', 'dim');
    await new Promise(r => setTimeout(r, 1200));
    addLog('Extracting key insights...', 'dim');
    await new Promise(r => setTimeout(r, 1000));
    addLog('Extraction complete', 'success');

    // Complete
    setCurrentPhase('complete');
    await new Promise(r => setTimeout(r, 300));
    addLog('Files written to output/', 'success');
    addLog('Pipeline complete in 14.2s', 'success');

    setResults({
      title: 'Understanding Transformer Architecture',
      transcript: sampleTranscript,
      summary: sampleSummary,
      metadata: {
        author: 'AI Explained',
        date: '2024-01-15',
        duration: '24m 18s',
        processed: new Date().toISOString().split('T')[0],
      }
    });
    
    setShowResults(true);
    setIsProcessing(false);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !isProcessing) {
      simulateProcessing();
    }
  };

  const togglePreview = (type) => {
    setActivePreview(activePreview === type ? null : type);
  };

  return (
    <div style={{
      minHeight: '100vh',
      background: 'linear-gradient(180deg, #0A0A08 0%, #12120F 100%)',
      color: '#E8DCC8',
      padding: '0',
      position: 'relative',
      overflow: 'hidden',
    }}>
      {/* Subtle grid overlay */}
      <div style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundImage: `
          linear-gradient(rgba(232, 168, 76, 0.02) 1px, transparent 1px),
          linear-gradient(90deg, rgba(232, 168, 76, 0.02) 1px, transparent 1px)
        `,
        backgroundSize: '50px 50px',
        pointerEvents: 'none',
      }} />

      {/* Vignette */}
      <div style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        background: 'radial-gradient(ellipse at center, transparent 0%, rgba(0,0,0,0.4) 100%)',
        pointerEvents: 'none',
      }} />

      <div style={{
        maxWidth: '900px',
        margin: '0 auto',
        padding: '60px 24px',
        position: 'relative',
      }}>
        {/* Header */}
        <header style={{
          marginBottom: '60px',
          animation: 'fadeIn 0.6s ease-out',
        }}>
          <div style={{
            fontFamily: '"JetBrains Mono", monospace',
            fontSize: '10px',
            textTransform: 'uppercase',
            letterSpacing: '0.2em',
            color: 'rgba(232, 168, 76, 0.5)',
            marginBottom: '12px',
          }}>
            ATLAS Meridia // Transcript Pipeline v1.0
          </div>
          <h1 style={{
            fontFamily: '"Instrument Serif", Georgia, serif',
            fontSize: '42px',
            fontWeight: '400',
            margin: '0 0 8px 0',
            letterSpacing: '-0.02em',
            background: 'linear-gradient(135deg, #E8DCC8 0%, #E8A84C 100%)',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
          }}>
            Transcript Pipeline
          </h1>
          <p style={{
            fontFamily: '"JetBrains Mono", monospace',
            fontSize: '13px',
            color: 'rgba(232, 168, 76, 0.6)',
            margin: 0,
            maxWidth: '500px',
            lineHeight: '1.6',
          }}>
            Extract transcripts and insights from YouTube videos using Scribe + Claude
          </p>
        </header>

        {/* Input Section */}
        <section style={{
          marginBottom: '40px',
          animation: 'fadeIn 0.6s ease-out 0.1s both',
        }}>
          <label style={{
            display: 'block',
            fontFamily: '"JetBrains Mono", monospace',
            fontSize: '10px',
            textTransform: 'uppercase',
            letterSpacing: '0.15em',
            color: 'rgba(232, 168, 76, 0.5)',
            marginBottom: '12px',
          }}>
            YouTube URL
          </label>
          <div style={{
            display: 'flex',
            gap: '12px',
          }}>
            <input
              type="text"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="https://youtube.com/watch?v=..."
              disabled={isProcessing}
              style={{
                flex: 1,
                background: 'rgba(232, 168, 76, 0.03)',
                border: '1px solid rgba(232, 168, 76, 0.2)',
                borderRadius: '4px',
                padding: '16px 20px',
                fontFamily: '"JetBrains Mono", monospace',
                fontSize: '14px',
                color: '#E8DCC8',
                outline: 'none',
                transition: 'all 0.2s ease',
              }}
              onFocus={(e) => {
                e.target.style.borderColor = 'rgba(232, 168, 76, 0.5)';
                e.target.style.background = 'rgba(232, 168, 76, 0.05)';
              }}
              onBlur={(e) => {
                e.target.style.borderColor = 'rgba(232, 168, 76, 0.2)';
                e.target.style.background = 'rgba(232, 168, 76, 0.03)';
              }}
            />
            <button
              onClick={simulateProcessing}
              disabled={isProcessing || !url.trim()}
              style={{
                background: isProcessing ? 'rgba(232, 168, 76, 0.1)' : 
                           !url.trim() ? 'rgba(232, 168, 76, 0.05)' :
                           'linear-gradient(135deg, #E8A84C 0%, #D4943C 100%)',
                border: 'none',
                borderRadius: '4px',
                padding: '16px 32px',
                fontFamily: '"JetBrains Mono", monospace',
                fontSize: '12px',
                fontWeight: '600',
                textTransform: 'uppercase',
                letterSpacing: '0.1em',
                color: isProcessing || !url.trim() ? 'rgba(232, 168, 76, 0.3)' : '#0A0A08',
                cursor: isProcessing || !url.trim() ? 'not-allowed' : 'pointer',
                transition: 'all 0.2s ease',
              }}
            >
              {isProcessing ? 'Processing...' : 'Process'}
            </button>
          </div>
        </section>

        {/* Waveform Visualizer */}
        <section style={{
          marginBottom: '40px',
          animation: 'fadeIn 0.6s ease-out 0.2s both',
        }}>
          <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: '12px',
          }}>
            <span style={{
              fontFamily: '"JetBrains Mono", monospace',
              fontSize: '10px',
              textTransform: 'uppercase',
              letterSpacing: '0.15em',
              color: 'rgba(232, 168, 76, 0.5)',
            }}>
              Signal Monitor
            </span>
            {currentPhase && (
              <PhaseIndicator currentPhase={currentPhase} phases={phases} />
            )}
          </div>
          <Waveform 
            isActive={isProcessing} 
            phase={currentPhase}
          />
        </section>

        {/* Log Output */}
        {logs.length > 0 && (
          <section style={{
            marginBottom: '40px',
            animation: 'fadeIn 0.3s ease-out',
          }}>
            <div style={{
              fontFamily: '"JetBrains Mono", monospace',
              fontSize: '10px',
              textTransform: 'uppercase',
              letterSpacing: '0.15em',
              color: 'rgba(232, 168, 76, 0.5)',
              marginBottom: '12px',
            }}>
              Process Log
            </div>
            <div style={{
              background: 'rgba(0, 0, 0, 0.3)',
              border: '1px solid rgba(232, 168, 76, 0.1)',
              borderRadius: '4px',
              padding: '16px 20px',
              maxHeight: '240px',
              overflowY: 'auto',
            }}>
              {logs.map((log, i) => (
                <LogEntry key={i} {...log} />
              ))}
            </div>
          </section>
        )}

        {/* Results */}
        {showResults && results && (
          <section style={{
            animation: 'slideUp 0.4s ease-out',
          }}>
            <div style={{
              fontFamily: '"JetBrains Mono", monospace',
              fontSize: '10px',
              textTransform: 'uppercase',
              letterSpacing: '0.15em',
              color: 'rgba(232, 168, 76, 0.5)',
              marginBottom: '12px',
            }}>
              Output Files
            </div>
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(2, 1fr)',
              gap: '16px',
            }}>
              <ResultCard
                title={results.title}
                type="transcript"
                content={results.transcript.slice(0, 200) + '...'}
                isActive={activePreview === 'transcript'}
                onView={() => togglePreview('transcript')}
              />
              <ResultCard
                title={results.title}
                type="summary"
                content={results.summary.slice(0, 200) + '...'}
                isActive={activePreview === 'summary'}
                onView={() => togglePreview('summary')}
              />
            </div>

            {/* Markdown Preview Pane */}
            {activePreview && (
              <MarkdownPreview
                type={activePreview}
                title={results.title}
                content={activePreview === 'transcript' ? results.transcript : results.summary}
                metadata={results.metadata}
                onClose={() => setActivePreview(null)}
              />
            )}
          </section>
        )}

        {/* Footer */}
        <footer style={{
          marginTop: '80px',
          paddingTop: '24px',
          borderTop: '1px solid rgba(232, 168, 76, 0.1)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          animation: 'fadeIn 0.6s ease-out 0.3s both',
        }}>
          <div style={{
            fontFamily: '"JetBrains Mono", monospace',
            fontSize: '10px',
            color: 'rgba(232, 168, 76, 0.3)',
          }}>
            Scribe v2 + Claude Sonnet 4.5
          </div>
          <div style={{
            fontFamily: '"JetBrains Mono", monospace',
            fontSize: '10px',
            color: 'rgba(232, 168, 76, 0.3)',
          }}>
            Docker Ready
          </div>
        </footer>
      </div>

      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=JetBrains+Mono:wght@400;500;600&family=Source+Serif+4:opsz,wght@8..60,400;8..60,500&display=swap');
        
        * {
          box-sizing: border-box;
        }
        
        ::placeholder {
          color: rgba(232, 168, 76, 0.3);
        }
        
        ::-webkit-scrollbar {
          width: 6px;
        }
        
        ::-webkit-scrollbar-track {
          background: rgba(232, 168, 76, 0.05);
        }
        
        ::-webkit-scrollbar-thumb {
          background: rgba(232, 168, 76, 0.2);
          border-radius: 3px;
        }
        
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(10px); }
          to { opacity: 1; transform: translateY(0); }
        }
        
        @keyframes slideUp {
          from { opacity: 0; transform: translateY(20px); }
          to { opacity: 1; transform: translateY(0); }
        }
        
        @keyframes slideDown {
          from { opacity: 0; transform: translateY(-10px); max-height: 0; }
          to { opacity: 1; transform: translateY(0); max-height: 800px; }
        }
      `}</style>
    </div>
  );
}
