using System;
using System.Diagnostics;

namespace Sifteo;

public class Log
{
	[Conditional("DEBUG")]
	public static void Debug(string msg, params object[] args)
	{
		Print("DEBUG", string.Format(msg, args));
	}

	public static void Info(string msg, params object[] args)
	{
		Print("INFO", string.Format(msg, args));
	}

	public static void Warning(string msg, params object[] args)
	{
		Print("WARNING", string.Format(msg, args));
	}

	public static void Error(string msg, params object[] args)
	{
		Print("ERROR", string.Format(msg, args));
	}

	[Conditional("DEBUG")]
	public static void Debug(string msg)
	{
		Print("DEBUG", msg);
	}

	public static void Info(string msg)
	{
		Print("INFO", msg);
	}

	public static void Warning(string msg)
	{
		Print("WARNING", msg);
	}

	public static void Error(string msg)
	{
		Print("ERROR", msg);
	}

	private static void Print(string label, string msg)
	{
		Console.WriteLine("[{0}] {1}", label, msg);
	}
}
