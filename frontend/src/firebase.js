// Import the functions you need from the SDKs you need
import { initializeApp } from "firebase/app";
// TODO: Add SDKs for Firebase products that you want to use
// https://firebase.google.com/docs/web/setup#available-libraries

const firebaseConfig = {
    apiKey: "AIzaSyC2QeFFRPn3HcdsoIxWLlm_Jy9Slfkcylg",
    authDomain: "fpl-wiz.firebaseapp.com",
    projectId: "fpl-wiz",
    storageBucket: "fpl-wiz.firebasestorage.app",
    messagingSenderId: "358338100594",
    appId: "1:358338100594:web:e67fc42c1be559b98cf1eb"
};

// Initialize Firebase
const app = initializeApp(firebaseConfig);

export default app;
