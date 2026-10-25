const express = require('express');
const axios = require('axios');

const app = express();
const userRouter = express.Router();

app.get('/health', (req, res) => res.send('ok'));
userRouter.post('/users', (req, res) => res.send('created'));
app.use('/api', userRouter);

async function callOut() {
  return axios.get('/not-a-route');
}

module.exports = { app, callOut };
