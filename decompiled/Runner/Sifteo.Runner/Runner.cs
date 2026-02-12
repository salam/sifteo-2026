using System;
using System.IO;
using System.Reflection;

namespace Sifteo.Runner;

internal class Runner
{
	public static void Main(string[] args)
	{
		int num = Array.IndexOf(args, "-A");
		if (num < 0 || args.Length < num + 1)
		{
			Usage();
			return;
		}
		string text = args[num + 1];
		if (!File.Exists(text))
		{
			Console.Error.WriteLine("Sifteo.Runner: {0} does not exist.", text);
			return;
		}
		try
		{
			BaseApp baseApp = null;
			Assembly assembly = Assembly.LoadFrom(text);
			Type[] types = assembly.GetTypes();
			foreach (Type type in types)
			{
				if (type.IsSubclassOf(typeof(BaseApp)))
				{
					baseApp = Activator.CreateInstance(type) as BaseApp;
					break;
				}
			}
			if (baseApp == null)
			{
				Console.Error.WriteLine("error: couldn't find any descendents of {0} in {1}", typeof(BaseApp).ToString(), text);
			}
			else
			{
				baseApp.Run();
			}
		}
		catch (Exception ex)
		{
			Console.WriteLine(ex.ToString());
		}
	}

	private static void Usage()
	{
		Console.Error.WriteLine("Sifteo.Runner");
		Console.Error.WriteLine("  usage: Runner.exe -R <absolute/path/to/game/folder> -A <relative/path/to/MyGreatApp.dll>");
	}
}
