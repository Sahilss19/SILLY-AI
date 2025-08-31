// static/script.js
document.addEventListener("DOMContentLoaded", () => {
    const recordBtn = document.getElementById("recordBtn");
    const statusDisplay = document.getElementById("statusDisplay");
    const chatLog = document.getElementById('chat-log');
    const settingsBtn = document.getElementById("settingsBtn");
    const settingsModal = new bootstrap.Modal(document.getElementById('settingsModal'));
    const saveKeysBtn = document.getElementById("saveKeysBtn");
    const personaSelect = document.getElementById("personaSelect");
    const personaLabel = document.getElementById("personaLabel");

    let isRecording = false;
    let ws = null;
    let audioContext;
    let mediaStream;
    let processor;
    let audioQueue = [];
    let isPlaying = false;
    
    // Load saved API keys
    const loadSettings = () => {
        document.getElementById("murfApiKey").value = localStorage.getItem("murfApiKey") || "";
        document.getElementById("assemblyAiApiKey").value = localStorage.getItem("assemblyAiApiKey") || "";
        document.getElementById("geminiApiKey").value = localStorage.getItem("geminiApiKey") || "";
        document.getElementById("serpApiKey").value = localStorage.getItem("serpApiKey") || "";
        document.getElementById("newsapi").value = localStorage.getItem("newsapi") || "";
        personaSelect.value = localStorage.getItem("selectedPersona") || "me";
        updatePersonaLabel();
    };

    const updatePersonaLabel = () => {
        const selectedOption = personaSelect.options[personaSelect.selectedIndex];
        personaLabel.textContent = selectedOption.textContent;
    };

    loadSettings();

    settingsBtn.addEventListener("click", () => {
        settingsModal.show();
    });

    saveKeysBtn.addEventListener("click", () => {
        localStorage.setItem("murfApiKey", document.getElementById("murfApiKey").value);
        localStorage.setItem("assemblyAiApiKey", document.getElementById("assemblyAiApiKey").value);
        localStorage.setItem("geminiApiKey", document.getElementById("geminiApiKey").value);
        localStorage.setItem("serpApiKey", document.getElementById("serpApiKey").value);
        localStorage.setItem("newsapi", document.getElementById("newsapi").value);
        settingsModal.hide();
        alert("API keys saved!");
    });
    
    personaSelect.addEventListener("change", () => {
        const selectedPersona = personaSelect.value;
        localStorage.setItem("selectedPersona", selectedPersona);
        updatePersonaLabel();
    });

    const addMessage = (text, type) => {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${type}`;
        messageDiv.textContent = text;
        chatLog.appendChild(messageDiv);
        chatLog.scrollTop = chatLog.scrollHeight;
    };

    const playNextInQueue = () => {
        if (audioQueue.length > 0) {
            isPlaying = true;
            const base64Audio = audioQueue.shift();
            // convert base64 string to ArrayBuffer
            const binaryString = atob(base64Audio);
            const len = binaryString.length;
            const bytes = new Uint8Array(len);
            for (let i = 0; i < len; i++) {
                bytes[i] = binaryString.charCodeAt(i);
            }
            const audioData = bytes.buffer;

            // ensure audioContext is created
            if (!audioContext) {
                audioContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
            }

            audioContext.decodeAudioData(audioData).then(buffer => {
                const source = audioContext.createBufferSource();
                source.buffer = buffer;
                source.connect(audioContext.destination);
                source.onended = playNextInQueue;
                source.start();
            }).catch(e => {
                console.error("Error decoding audio data:", e);
                playNextInQueue();
            });
        } else {
            isPlaying = false;
        }
    };

    const startRecording = async () => {
        const apiKeys = {
            murf: localStorage.getItem("murfApiKey"),
            assemblyai: localStorage.getItem("assemblyAiApiKey"),
            gemini: localStorage.getItem("geminiApiKey"),
            serpapi: localStorage.getItem("serpApiKey"),
            newsapi: localStorage.getItem("newsapi")
        };
        const selectedPersona = localStorage.getItem("selectedPersona") || "me";

        // It's OK if keys are empty as server might have them; warn user but allow
        // If you require keys client-side, uncomment this block:
        // if (!apiKeys.murf || !apiKeys.assemblyai || !apiKeys.gemini) {
        //     alert("Please set at least Murf, AssemblyAI, and Gemini API keys in the settings or configure them server-side.");
        //     return;
        // }

        try {
            mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
            audioContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });

            const source = audioContext.createMediaStreamSource(mediaStream);
            processor = audioContext.createScriptProcessor(4096, 1, 1);
            source.connect(processor);
            processor.connect(audioContext.destination);
            processor.onaudioprocess = (e) => {
                const inputData = e.inputBuffer.getChannelData(0);
                const pcmData = new Int16Array(inputData.length);
                for (let i = 0; i < inputData.length; i++) {
                    const s = Math.max(-1, Math.min(1, inputData[i]));
                    pcmData[i] = s < 0 ? s * 32768 : s * 32767;
                }
                if (ws && ws.readyState === WebSocket.OPEN) {
                    try {
                        ws.send(pcmData.buffer);
                    } catch (err) {
                        console.error("WebSocket send error:", err);
                    }
                }
            };

            const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
            ws = new WebSocket(`${wsProtocol}//${window.location.host}/ws`);

            ws.onopen = () => {
                // send config - server may override or use its own keys
                ws.send(JSON.stringify({ type: "config", keys: apiKeys, persona: selectedPersona }));
            };

            ws.onmessage = (event) => {
                try {
                    const msg = JSON.parse(event.data);
                    if (msg.type === "assistant") {
                        addMessage(msg.text, "assistant");
                    } else if (msg.type === "final") {
                        addMessage(msg.text, "user");
                    } else if (msg.type === "audio") {
                        audioQueue.push(msg.b64);
                        if (!isPlaying) {
                            playNextInQueue();
                        }
                    } else if (msg.type === "llm_error" || msg.type === "error") {
                        addMessage(msg.text || "An error occurred.", "assistant");
                    }
                } catch (err) {
                    console.error("Error processing websocket message:", err);
                }
            };

            ws.onclose = () => {
                console.log("WebSocket closed");
            };

            ws.onerror = (e) => {
                console.error("WebSocket error:", e);
            };

            isRecording = true;
            recordBtn.classList.add("recording");
            statusDisplay.textContent = "Listening...";
        } catch (error) {
            console.error("Could not start recording:", error);
            alert("Microphone access is required to use the voice agent.");
        }
    };

    const stopRecording = () => {
        if (processor) {
            try { processor.disconnect(); } catch (e) {}
        }
        if (mediaStream) {
            try { mediaStream.getTracks().forEach(track => track.stop()); } catch (e) {}
        }
        if (ws) {
            try { ws.close(); } catch (e) {}
        }
        
        isRecording = false;
        recordBtn.classList.remove("recording");
        statusDisplay.textContent = "Ready to chat!";
    };

    recordBtn.addEventListener("click", () => {
        if (isRecording) {
            stopRecording();
        } else {
            startRecording();
        }
    });

    // Initial message for the user
    addMessage("Mic check… Yo buddy, drop your words 🎤", "assistant");
});
