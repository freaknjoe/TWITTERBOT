const express = require("express");
const app = express();
app.use(express.urlencoded({ extended: true }));
app.use(express.json());
const path = require("path");
const { get } = require("axios");

const { Firestore } = require("@google-cloud/firestore");
const firestoreDb = new Firestore();

const fs = require("fs");
const util = require("util");
const { spinnerSvg } = require("./spinnerSvg.js");

const service = process.env.K_SERVICE;
const revision = process.env.K_REVISION;

app.use(express.static("public"));

app.get("/edit", async (req, res) => {
    res.send(`<form hx-post="/update" hx-target="this" hx-swap="outerHTML">
                <div>
  <p>
    <label>Name</label>    
    <input class="border-2" type="text" name="name" value="Cloud">
    </p><p>
    <label>Town</label>    
    <input class="border-2" type="text" name="town" value="Nibelheim">
    </p>
  </div>
  <div class="flex items-center mr-[10px] mt-[10px]">
  <button class="btn bg-blue-500 text-white px-4 py-2 rounded-lg text-center text-sm font-medium mr-[10px]">Submit</button>
  <button class="btn bg-gray-200 text-gray-800 px-4 py-2 rounded-lg text-center text-sm font-medium mr-[10px]" hx-get="cancel">Cancel</button>  
                ${spinnerSvg} 
                </div>
  </form>`);
});

app.post("/update", async function (req, res) {
    let name = req.body.name;
    let town = req.body.town;
    const doc = firestoreDb.doc(`demo/${name}`);

    //TODO: fix this bug
    await doc.set({
        name: name
        /* town: town */
    });

    res.send(`<div hx-target="this" hx-swap="outerHTML" hx-indicator="spinner">
                <p>
                <div><label>Name</label>: ${name}</div>
                </p><p>
                <div><label>Town</label>: ${town}</div>
                </p>
                <button
                    hx-get="/edit"
                    class="bg-blue-500 text-white px-4 py-2 rounded-lg text-sm font-medium mt-[10px]"
                >
                    Click to update
                </button>               
            </div>`);
});

app.get("/cancel", (req, res) => {
    res.send(`<div hx-target="this" hx-swap="outerHTML">
                <p>
                <div><label>Name</label>: Cloud</div>
                </p><p>
                <div><label>Town</label>: Nibelheim</div>
                </p>
                <div>
                <button
                    hx-get="/edit"
                    class="bg-blue-500 text-white px-4 py-2 rounded-lg text-sm font-medium mt-[10px]"
                >
                    Click to update
                </button>                
                </div>
            </div>`);
});

const port = parseInt(process.env.PORT) || 8080;
app.listen(port, async () => {
    console.log(`booth demo: listening on port ${port}`);

    //serviceMetadata = helper();
});

app.get("/helper", async (req, res) => {
    let region = "";
    let projectId = "";
    let div = "";

    try {
        // Fetch the token to make a GCF to GCF call
        const response1 = await get(
            "http://metadata.google.internal/computeMetadata/v1/project/project-id",
            {
                headers: {
                    "Metadata-Flavor": "Google"
                }
            }
        );

        // Fetch the token to make a GCF to GCF call
        const response2 = await get(
            "http://metadata.google.internal/computeMetadata/v1/instance/region",
            {
                headers: {
                    "Metadata-Flavor": "Google"
                }
            }
        );

        projectId = response1.data;
        let regionFull = response2.data;
        const index = regionFull.lastIndexOf("/");
        region = regionFull.substring(index + 1);

        div = `
        <div>
        This created the revision <code>${revision}</code> of the 
        Cloud Run service <code>${service}</code> in <code>${region}</code>
        for project <code>${projectId}</code>.
        </div>`;
    } catch (ex) {
        // running locally
        div = `<div> This is running locally.</div>`;
    }

    res.send(div);
});

