#!/usr/bin/env node

/*
Supabase Function for Strategy Management
This integrates the strategy management API into Supabase
*/

import { createClient } from "https://esm.sh/@supabase/supabase-js@2.39.0";

export default async function handler(req, res) {
  // Initialize Supabase client with service role key from environment
  const supabaseUrl = process.env.SUPABASE_URL;
  const supabaseKey = process.env.SUPABASE_SERVICE_ROLE_KEY;
  const supabase = createClient(supabaseUrl, supabaseKey);

  // Handle CORS preflight
  if (req.method === "OPTIONS") {
    return res.status(200).json({ message: "OK" });
  }

  // Handle different HTTP methods
  try {
    switch (req.method) {
      case "GET":
        return await handleGet(req, res, supabase);
      case "POST":
        return await handlePost(req, res, supabase);
      case "PUT":
        return await handlePut(req, res, supabase);
      case "DELETE":
        return await handleDelete(req, res, supabase);
      default:
        return res.status(405).json({ error: "Method not allowed" });
    }
  } catch (error) {
    console.error("Strategy API error:", error);
    return res.status(500).json({ error: "Internal server error" });
  }
}

// Handle GET requests - fetch strategies
async function handleGet(req, res, supabase) {
  const { data, error } = await supabase
    .from("strategies")
    .select("*")
    .order("created_at", { ascending: false });

  if (error) {
    console.error("GET strategies error:", error);
    return res.status(500).json({ error: error.message });
  }

  return res.status(200).json({
    strategies: data,
    count: data.length,
  });
}

// Handle POST requests - create new strategy
async function handlePost(req, res, supabase) {
  const { name, description, parameters, type } = req.body;

  if (!name) {
    return res.status(400).json({ error: "Name is required" });
  }

  const { data, error } = await supabase
    .from("strategies")
    .insert([
      {
        name,
        description,
        parameters,
        type,
        created_at: new Date().toISOString(),
      },
    ])
    .select();

  if (error) {
    console.error("POST strategy error:", error);
    return res.status(500).json({ error: error.message });
  }

  return res.status(201).json({
    strategy: data[0],
  });
}

// Handle PUT requests - update strategy
async function handlePut(req, res, supabase) {
  const { id, name, description, parameters, type } = req.body;

  if (!id) {
    return res.status(400).json({ error: "ID is required to update strategy" });
  }

  const { data, error } = await supabase
    .from("strategies")
    .update({
      name,
      description,
      parameters,
      type,
      updated_at: new Date().toISOString(),
    })
    .eq("id", id)
    .select();

  if (error) {
    console.error("PUT strategy error:", error);
    return res.status(500).json({ error: error.message });
  }

  if (data.length === 0) {
    return res.status(404).json({ error: "Strategy not found" });
  }

  return res.status(200).json({
    strategy: data[0],
  });
}

// Handle DELETE requests - delete strategy
async function handleDelete(req, res, supabase) {
  const { id } = req.body;

  if (!id) {
    return res.status(400).json({ error: "ID is required to delete strategy" });
  }

  const { data, error } = await supabase
    .from("strategies")
    .delete()
    .eq("id", id)
    .select();

  if (error) {
    console.error("DELETE strategy error:", error);
    return res.status(500).json({ error: error.message });
  }

  return res.status(200).json({
    message: "Strategy deleted successfully",
    deleted: data[0],
  });
}
