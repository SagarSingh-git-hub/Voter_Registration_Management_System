// Import the functions you need from the SDKs you need
import { initializeApp } from "https://www.gstatic.com/firebasejs/10.7.1/firebase-app.js";
import { 
    getAuth, 
    createUserWithEmailAndPassword, 
    signInWithEmailAndPassword, 
    signInWithPhoneNumber, 
    RecaptchaVerifier, 
    signOut, 
    onAuthStateChanged 
} from "https://www.gstatic.com/firebasejs/10.7.1/firebase-auth.js";

// Your web app's Firebase configuration
const firebaseConfig = {
  apiKey: window.ENV.FIREBASE_API_KEY,
  authDomain: window.ENV.FIREBASE_AUTH_DOMAIN,
  projectId: window.ENV.FIREBASE_PROJECT_ID,
  storageBucket: window.ENV.FIREBASE_STORAGE_BUCKET,
  messagingSenderId: window.ENV.FIREBASE_MESSAGING_SENDER_ID,
  appId: window.ENV.FIREBASE_APP_ID
};

// Initialize Firebase
const app = initializeApp(firebaseConfig);
const auth = getAuth(app);

// --- Supabase Integration ---
const SUPABASE_URL = window.ENV.SUPABASE_URL;
const SUPABASE_ANON_KEY = window.ENV.SUPABASE_ANON_KEY;
let supabase = null;

if (typeof createClient !== 'undefined') {
    supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
} else if (window.supabase) {
    // If loaded via CDN, it might be window.supabase.createClient
    supabase = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
} else {
    console.warn("Supabase SDK not loaded");
}

/**
 * Verifies Firebase Token via Edge Function and Syncs to Supabase DB
 * @param {object} user - Firebase User object
 */
async function verifyAndSyncUser(user) {
    if (!user) return;
    
    console.log("Starting Secure Verification & Sync...");
    try {
        // STEP 7: Frontend Call (Secure Pattern)
        const token = await user.getIdToken();
        const verifyUrl = `${SUPABASE_URL}/functions/v1/verify-firebase-token`;
        
        const res = await fetch(verifyUrl, {
            headers: {
                Authorization: `Bearer ${token}`
            }
        });
        
        if (res.status === 401) {
            throw new Error("Unauthorized: Invalid or expired token");
        }
        
        const data = await res.json();
        console.log("Token Verified by Edge Function:", data);
        
        // STEP 8: Database Sync After Verification
        if (supabase) {
            console.log("Syncing to Supabase DB...");
            const { error } = await supabase.from("users").upsert({
                firebase_uid: data.uid,
                email: data.email,
                phone: data.phone || user.phoneNumber, // Fallback if claim is missing
                last_login: new Date().toISOString()
            });
            
            if (error) {
                console.error("Supabase Sync Error:", error);
                // We don't block login on sync error, but we log it
            } else {
                console.log("User Synced to Supabase ✅");
            }
        } else {
            console.warn("Supabase Client not ready, skipping sync.");
        }
        
        return data;
        
    } catch (error) {
        console.error("Verification Failed:", error);
        throw error;
    }
}

// Expose functions globally for legacy inline scripts (login.html, register.html)
window.firebaseAuth = {
    auth: auth,
    createUserWithEmailAndPassword: createUserWithEmailAndPassword,
    signInWithEmailAndPassword: signInWithEmailAndPassword,
    signInWithPhoneNumber: signInWithPhoneNumber,
    RecaptchaVerifier: RecaptchaVerifier,
    signOut: signOut,
    onAuthStateChanged: onAuthStateChanged,
    verifyAndSyncUser: verifyAndSyncUser, // Added this
    supabase: supabase
};

// Also expose 'auth' directly as 'window.auth' for backward compatibility if needed, 
// though the new logic should use window.firebaseAuth.auth
window.auth = auth;

console.log("Firebase Initialized (Module Mode v10.7.1)");
