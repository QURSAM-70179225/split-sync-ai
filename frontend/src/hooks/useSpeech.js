import { useCallback, useEffect, useRef, useState } from "react";

/** Browser speech-to-text (Web Speech API). Works in Chrome, Edge and Safari. */
export function useSpeech({ onFinal, lang = "en-US" } = {}) {
  const Recognition = typeof window !== "undefined" && (window.SpeechRecognition || window.webkitSpeechRecognition);
  const [listening, setListening] = useState(false);
  const [interim, setInterim] = useState("");
  const rec = useRef(null);
  const finalCb = useRef(onFinal);
  finalCb.current = onFinal;

  useEffect(() => () => rec.current?.abort(), []);

  const start = useCallback(() => {
    if (!Recognition || listening) return;
    const r = new Recognition();
    r.lang = lang;
    r.interimResults = true;
    r.continuous = false;
    r.onresult = (e) => {
      let text = "";
      let isFinal = false;
      for (const res of e.results) {
        text += res[0].transcript;
        if (res.isFinal) isFinal = true;
      }
      setInterim(text);
      if (isFinal) finalCb.current?.(text.trim());
    };
    r.onend = () => {
      setListening(false);
      setInterim("");
    };
    r.onerror = () => setListening(false);
    rec.current = r;
    r.start();
    setListening(true);
  }, [Recognition, lang, listening]);

  const stop = useCallback(() => rec.current?.stop(), []);

  return { supported: Boolean(Recognition), listening, interim, start, stop };
}
