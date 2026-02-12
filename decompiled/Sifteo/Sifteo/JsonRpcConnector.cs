using System;
using System.Collections.Generic;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Threading;
using JsonFx.Json;
using JsonFx.Serialization;

namespace Sifteo;

internal class JsonRpcConnector
{
	public const int DEFAULT_PORT = 7000;

	public const string DEFAULT_ADDRESS = "127.0.0.1";

	private string mAddress;

	private int mPort;

	private TcpClient mClient;

	private JsonRpcService mService;

	private JsonWriter mJsonWriter = new JsonWriter();

	private StreamWriter mStreamWriter;

	private StreamReader mStreamReader;

	private IAsyncResult mJsonReadResult;

	private Func<TextReader, object> mReadMethod = new JsonReader().Read;

	internal WaitHandle DataRxWaitHandle
	{
		get
		{
			if (mJsonReadResult == null || mJsonReadResult.IsCompleted)
			{
				mJsonReadResult = mReadMethod.BeginInvoke(mStreamReader, null, null);
			}
			return mJsonReadResult.AsyncWaitHandle;
		}
	}

	public JsonRpcConnector(JsonRpcService service)
		: this(service, "127.0.0.1", 7000)
	{
	}

	public JsonRpcConnector(JsonRpcService service, string address)
		: this(service, address, 7000)
	{
	}

	public JsonRpcConnector(JsonRpcService service, string address, int port)
	{
		mService = service;
		mAddress = address;
		mPort = port;
	}

	public bool Send(object o)
	{
		if (mClient == null || !mClient.Connected)
		{
			return false;
		}
		try
		{
			mJsonWriter.Write(o, mStreamWriter);
			mStreamWriter.Flush();
		}
		catch (IOException)
		{
			Close();
		}
		return true;
	}

	public void StartListening()
	{
		try
		{
			TcpListener tcpListener = new TcpListener(IPAddress.Parse(mAddress), mPort);
			tcpListener.Start();
			Console.WriteLine("+{0}:{1}", mAddress, mPort);
			mClient = tcpListener.AcceptTcpClient();
			mStreamWriter = new StreamWriter(mClient.GetStream());
			mStreamReader = new StreamReader(mClient.GetStream());
			mService.HandleConnection();
		}
		catch (Exception ex)
		{
			Console.WriteLine(ex.ToString());
		}
	}

	internal void CancelWaitForData()
	{
		mClient.Close();
	}

	internal void HandleDataRx()
	{
		try
		{
			if (!(mReadMethod.EndInvoke(mJsonReadResult) is Dictionary<string, object> msg))
			{
				Close();
			}
			else
			{
				mService.OnJsonMsgRxed(msg);
			}
		}
		catch (DeserializationException)
		{
			Close();
		}
	}

	private void Close()
	{
		mService.HandleDisconnection();
		mClient.Close();
	}
}
